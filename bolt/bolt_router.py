from collections import defaultdict
import json
from os import environ
from random import choice
from urllib3 import PoolManager
from threading import Lock

import copy
import random
import sys 
import sched
import time
import datetime
import string
import requests
from functools import wraps
from threading import Thread
from urlparse import urlsplit
from urlparse import urlunsplit

from botocore.auth import SigV4Auth, SIGV4_TIMESTAMP, logger
from botocore.awsrequest import AWSRequest
from botocore.exceptions import UnknownEndpointError
from botocore.session import get_session
from botocore.httpsession import URLLib3Session

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# throws Exception if not found
def get_region():
    region = environ.get('AWS_REGION')
    if region is not None:
        return region
    
    return _default_get('http://169.254.169.254/latest/meta-data/placement/region')

# throws Exception if not found
def get_availability_zone_id():
    zone = environ.get('AWS_ZONE_ID')
    if zone is not None:
        return zone
    
    return _default_get('http://169.254.169.254/latest/meta-data/placement/availability-zone-id')


def _default_get(url):
    try:
        http = PoolManager(timeout=3.0)
        resp = http.request('GET', url, retries=2)
        return resp.data.decode('utf-8')
    except Exception as e:
        raise e


def async_function(func):
    @wraps(func)
    def async_func(*args, **kwargs):
        if sys.version_info[0] == 2:
            func_hl = Thread(target=func, args=args, kwargs=kwargs)
            func_hl.daemon = True
        else:
            func_hl = Thread(daemon=True, target=func, args=args, kwargs=kwargs)

        func_hl.start()

        return func_hl
    return async_func


def schedule(interval):
    def decorator(func):
        def periodic(scheduler, interval, action, actionargs=()):
            scheduler.enter(interval, 1, periodic,
                            (scheduler, interval, action, actionargs))
            action(*actionargs)

        @wraps(func)
        def wrap(*args, **kwargs):
            scheduler = sched.scheduler(time.time, time.sleep)
            periodic(scheduler, interval, func)
            scheduler.run()
        return wrap
    return decorator

class BoltSession(URLLib3Session):
    """
    We need to override the default behavior of the URLLib3Session class to accept a different hostname for SSL verification,
    since we want to connect to a specific IP without relying on DNS. See https://urllib3.readthedocs.io/en/latest/advanced-usage.html#custom-sni-hostname
    """
    def __init__(self, bolt_hostname, **kwargs):
        self._bolt_hostname = bolt_hostname
        super(BoltSession, self).__init__(**kwargs)


    def _get_pool_manager_kwargs(self, **extra_kwargs):
        # Add 'server_hostname' arg to use for SSL validation
        extra_kwargs.update(server_hostname=self._bolt_hostname)
        return super(BoltSession, self)._get_pool_manager_kwargs(**extra_kwargs)


    def send(self, request):
        # start: do bolt request
        request.headers['Host'] = self._bolt_hostname
        for key in request.headers.keys():
            if key == "Expect":
                continue
            request.headers[key] = request.headers[key]

        request.headers["x-set-response-status-code"] = "405"
        return super(BoltSession, self).send(request)

        
def roundTime(dt=None, dateDelta=datetime.timedelta(minutes=1)):
    """Round a datetime object to a multiple of a timedelta
    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    """
    roundTo = dateDelta.total_seconds()

    if dt == None : dt = datetime.datetime.now()
    seconds = (dt - dt.min).seconds
    # // is a floor division, not a comment on following line:
    rounding = (seconds+roundTo/2) // roundTo * roundTo
    return dt + datetime.timedelta(0,rounding-seconds,-dt.microsecond)

def _get_datatime_delta():
    return datetime.timedelta(minutes=10)

class BoltSigV4Auth(SigV4Auth):
    def __init__(self, *args, **kwargs):
        super(BoltSigV4Auth, self).__init__(*args, **kwargs)
        self.__bolt_timestamp_pin_duration = datetime.timedelta(minutes=10)
        self.__bolt_random_offset = datetime.timedelta(seconds=random.randint(0, self.__bolt_timestamp_pin_duration.total_seconds()))

    # From https://github.com/boto/botocore/blob/e720eefba94963f373b3ff7c888a89bea06cd4a1/botocore/auth.py
    def add_auth(self, request):
        if self.credentials is None:
            raise NoCredentialsError()
        # datetime_now = datetime.datetime.utcnow()

        # Sign with a fixed time so that auth header can be cached
        # This fixed time is offset by a random interval to smooth out refreshes across clients
        datetime_now = roundTime(datetime.datetime.utcnow() - self.__bolt_random_offset, self.__bolt_timestamp_pin_duration) + self.__bolt_random_offset

        request.context['timestamp'] = datetime_now.strftime(SIGV4_TIMESTAMP)
        # This could be a retry.  Make sure the previous
        # authorization header is removed first.
        self._modify_request_before_signing(request)
        canonical_request = self.canonical_request(request)
        logger.debug("Calculating signature using v4 auth.")
        logger.debug('CanonicalRequest:\n%s', canonical_request)
        string_to_sign = self.string_to_sign(request, canonical_request)
        logger.debug('StringToSign:\n%s', string_to_sign)
        signature = self.signature(string_to_sign, request)
        logger.debug('Signature:\n%s', signature)

        self._inject_signature_to_request(request, signature)


class BoltRouter:
    """A stateful request mutator for Bolt S3 proxy.

    Sends S3 requests to an alternative Bolt URL based on configuration.

    To set a Bolt S3 proxy URL, run `aws [--profile PROFILE] configure set bolt.url http://localhost:9000`.
    """

    # const ordering to use when selecting endpoints
    PREFERRED_READ_ENDPOINT_ORDER = ("main_read_endpoints", "main_write_endpoints", "failover_read_endpoints", "failover_write_endpoints")
    PREFERRED_WRITE_ENDPOINT_ORDER = ("main_write_endpoints", "failover_write_endpoints")

    def __init__(self, scheme, service_url, hostname, region, az_id, update_interval=-1):
        # The scheme (parsed at bootstrap from the AWS config).
        self._scheme = scheme
        # The service discovery host (parsed at bootstrap from the AWS config).
        self._service_url = service_url
        # the hostname to use for SSL validation when connecting directly to Bolt IPs
        self._hostname = hostname
        # Availability zone ID to use (may be none)
        self._az_id = az_id
        self._region = region

        # Map of Bolt endpoints to use for connections, and mutex protecting it
        self._bolt_endpoints = defaultdict(list)
        self._mutex = Lock()

        self._get_endpoints()

        self._auth = BoltSigV4Auth(get_session().get_credentials().get_frozen_credentials(), "s3", region)
        # Each client uses a random 4-char long prefix to randomize the S3 path used for auth lookups
        self._prefix = ''.join(random.choice(string.ascii_uppercase  + string.ascii_lowercase + string.digits) for _ in range(4))

        if update_interval > 0:
            @async_function
            @schedule(update_interval)
            def update_endpoints():
                try: 
                    self._get_endpoints()
                except Exception as e:
                    sys.stderr.write(str(e))
                    sys.stderr.flush()
                    print(e)
            update_endpoints()

    def send(self, *args, **kwargs):
        # Dispatches to the configured Bolt scheme and host.
        prepared_request = kwargs['request']
        # print("incoming request")
        # print(prepared_request)
        incoming_request = copy.deepcopy(prepared_request)
        _, _, path, query, fragment = urlsplit(prepared_request.url)
        host = self._select_endpoint(prepared_request.method)
        if self._scheme == "http":
            host = host+":9000"

        prepared_request.url = urlunsplit((self._scheme, host, path, query, fragment))

        # TODO Fix handling requests without bucket names (like list)
        source_bucket = path.split('/')[1]

        # Construct the HEAD request that would be sent out by Bolt for authentication
        # print("making a head request")
        request = AWSRequest(
          method='HEAD',
          url='https://s3.{}.amazonaws.com/{}/{}/auth'.format(self._region,source_bucket, self._prefix),
          data=None,
          params=None,
          headers=None
        )
        # S3 requests always need the Content-SHA header included in the signature. As the HEAD request has no
        # content, it's just the SHA of an empty string and it's always the value below.
        # https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
        request.headers['X-Amz-Content-Sha256'] = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

        self._auth.add_auth(request)

        # print("done making head request")

        for key in ["X-Amz-Date", "Authorization", "X-Amz-Security-Token", "X-Amz-Content-Sha256"]:
          if request.headers.get(key):
            prepared_request.headers[key] = request.headers[key]
        prepared_request.headers['X-Bolt-Auth-Prefix'] = self._prefix

        # print("prepared request body: ", str(prepared_request.body))
        # print("prepared request url: ", prepared_request.url)
        # print("prepared request headers: ", prepared_request.headers)

        # print("path: ", path)
        path_without_bucket = "".join(path.split('/')[2:])
        # print("path without bucket: ", path_without_bucket)

        # raw boto uses past style
        # DEBUG:botocore.utils:Updating URI from https://s3.amazonaws.com/km-us-west-2/kote.txt to https://s3.us-west-2.amazonaws.com/km-us-west-2/kote.txt

        # virtual hosted style
        # new_url =  "https://{}.s3.{}.amazonaws.com/{}".format(source_bucket, self._region, path_without_bucket)

        # pathstyle
        # new_url = "https://s3.{}.amazonaws.com{}".format(self._region, path)
        # new_url = "https://google.com"
        # print("new url: ", new_url)

        # resp = requests.get(new_url)
        # print(resp.status_code)
        # print(resp.text)

        # failover_request = AWSRequest(
        #     method=prepared_request.method,
        #     url=new_url,
        #     data="kote-from-code", # prepared_request.body,
        #     params=None,
        #     headers=None
        # )
        # self._auth.add_auth(failover_request)
        
        # prepared_failover_request = failover_request.prepare()
        # prepared_failover_request.headers["Host"] = "https://{}.s3.{}.amazonaws.com".format(source_bucket, self._region)
        # prepared_failover_request.headers["Host"] = "https://s3.{}.amazonaws.com".format(self._region)

        # print("prepared failover request body: ", str(prepared_failover_request.body))
        # print("prepared failover request url: ", prepared_failover_request.url)
        # print("prepared failover request headers: ", prepared_failover_request.headers)
        

        # send this request with our custom session options
        # if an AWSResponse is returned directly from a `before-send` event handler function, 
        # botocore will use that as the response without making its own request.
        try: 
          bolt_response =  BoltSession(self._hostname, verify=ssl_verify).send(prepared_request)
          if 400 <= bolt_response.status_code < 500:
              logger.debug("failing over to aws, bolt response code was 4xx", extra={"status_code": bolt_response.status_code})
              return URLLib3Session().send(incoming_request)
          return bolt_response
        except Exception as e:
          logger.debug("failing over to aws cause of exception", extra={"exception": e})
          return URLLib3Session().send(incoming_request)

    def _get_endpoints(self):
        try:
            service_url = '{}/services/bolt?az={}'.format(self._service_url, self._az_id)
            resp = _default_get(service_url)
            endpoint_map = json.loads(resp)
            with self._mutex: 
                self._bolt_endpoints = defaultdict(list, endpoint_map)
        except Exception as e:
            # pass
            self._bolt_endpoints = defaultdict(list)
            # raise e

    def _select_endpoint(self, method):
        preferred_order = self.PREFERRED_READ_ENDPOINT_ORDER if method in {"GET", "HEAD"} else self.PREFERRED_WRITE_ENDPOINT_ORDER
        
        with self._mutex: 
            for endpoints in preferred_order:
                if self._bolt_endpoints[endpoints]:
                    # use random choice for load balancing
                    return choice(self._bolt_endpoints[endpoints])
        # if we reach this point, no endpoints are available
        raise UnknownEndpointError(service_name='bolt', region_name=self._az_id)
