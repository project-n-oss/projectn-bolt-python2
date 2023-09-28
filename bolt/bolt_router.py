import copy
import datetime
import json
import random
import sched
import string
import sys
import time
from collections import defaultdict
from functools import wraps
from os import environ
from random import choice
from threading import Lock, Thread

import urllib3
from botocore.auth import SIGV4_TIMESTAMP, SigV4Auth, logger
from botocore.awsrequest import AWSRequest
from botocore.exceptions import UnknownEndpointError
from botocore.httpsession import URLLib3Session
from botocore.session import get_session
from urllib3.util.retry import Retry
from urlparse import urlsplit, urlunsplit

EC2_INSTANCE_METADATA_API_BASE_URL = "http://169.254.169.254"

http_pool = urllib3.PoolManager(
    retries=Retry(
        total=5,  # Total number of retries
        backoff_factor=0.1,  # Time to sleep between retries (0.1s, 0.2s, 0.4s, ...)
    )
)


# throws Exception on failure
def get_metadata_api_token():
    url = "{}/latest/api/token".format(EC2_INSTANCE_METADATA_API_BASE_URL)
    headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
    response = http_pool.request('PUT', url, headers=headers)
    if response.status == 200:
        token = response.data.decode('utf-8')
        return token
    else:
        raise Exception(
            "Failed to fetch token. Status code: {}".format(response.status)
        )


# throws Exception on failure
def get_region():
    region = environ.get('AWS_REGION')
    if region is not None:
        return region
    token = get_metadata_api_token()
    headers = {"X-aws-ec2-metadata-token": token}
    url = "{}/latest/meta-data/placement/region".format(
        EC2_INSTANCE_METADATA_API_BASE_URL
    )
    response = http_pool.request("GET", url, headers=headers)
    if response.status == 200:
        return response.data.decode('utf-8')
    else:
        raise Exception(
            "Failed to fetch region. Status code: {}".format(response.status)
        )


# throws Exception if not found
def get_availability_zone_id():
    zone = environ.get('AWS_ZONE_ID')
    if zone is not None:
        return zone

    token = get_metadata_api_token()
    headers = {"X-aws-ec2-metadata-token": token}
    url = "{}/latest/meta-data/placement/availability-zone-id".format(
        EC2_INSTANCE_METADATA_API_BASE_URL
    )
    response = http_pool.request("GET", url, headers=headers)
    if response.status == 200:
        return response.data.decode('utf-8')
    else:
        raise Exception(
            "Failed to fetch availability zone id. Status code: {}".format(
                response.status
            )
        )


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
            scheduler.enter(
                interval, 1, periodic, (scheduler, interval, action, actionargs)
            )
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
        request.headers['Host'] = self._bolt_hostname
        for key in request.headers.keys():
            if key == "Expect":
                continue
            request.headers[key] = request.headers[key]

        return super(BoltSession, self).send(request)


def roundTime(dt=None, dateDelta=datetime.timedelta(minutes=1)):
    """Round a datetime object to a multiple of a timedelta
    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    """
    roundTo = dateDelta.total_seconds()

    if dt == None:
        dt = datetime.datetime.now()
    seconds = (dt - dt.min).seconds
    # // is a floor division, not a comment on following line:
    rounding = (seconds + roundTo / 2) // roundTo * roundTo
    return dt + datetime.timedelta(0, rounding - seconds, -dt.microsecond)


def _get_datatime_delta():
    return datetime.timedelta(minutes=10)


class BoltSigV4Auth(SigV4Auth):
    def __init__(self, *args, **kwargs):
        super(BoltSigV4Auth, self).__init__(*args, **kwargs)
        self.__bolt_timestamp_pin_duration = datetime.timedelta(minutes=10)
        self.__bolt_random_offset = datetime.timedelta(
            seconds=random.randint(
                0, self.__bolt_timestamp_pin_duration.total_seconds()
            )
        )

    # From https://github.com/boto/botocore/blob/e720eefba94963f373b3ff7c888a89bea06cd4a1/botocore/auth.py
    def add_auth(self, request):
        if self.credentials is None:
            raise NoCredentialsError()
        # datetime_now = datetime.datetime.utcnow()

        # Sign with a fixed time so that auth header can be cached
        # This fixed time is offset by a random interval to smooth out refreshes across clients
        datetime_now = (
            roundTime(
                datetime.datetime.utcnow() - self.__bolt_random_offset,
                self.__bolt_timestamp_pin_duration,
            )
            + self.__bolt_random_offset
        )

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
    PREFERRED_READ_ENDPOINT_ORDER = (
        "main_read_endpoints",
        "main_write_endpoints",
        "failover_read_endpoints",
        "failover_write_endpoints",
    )
    PREFERRED_WRITE_ENDPOINT_ORDER = (
        "main_write_endpoints",
        "failover_write_endpoints",
    )

    def __init__(
        self,
        scheme,
        quicksilver_api_base_url,
        hostname,
        region,
        az_id,
        update_interval=-1,
    ):
        # The scheme (parsed at bootstrap from the AWS config).
        self._scheme = scheme
        # The service discovery host (parsed at bootstrap from the AWS config).
        self._quicksilver_api_base_url = quicksilver_api_base_url
        # the hostname to use for SSL validation when connecting directly to Bolt IPs
        self._hostname = hostname
        # Availability zone ID to use (may be none)
        self._az_id = az_id
        self._region = region

        if self._az_id is None:
            # None obj formats as "None" into the string so let's not include it if it's None
            self._quicksilver_url = '{}/services/bolt'.format(
                self._quicksilver_api_base_url
            )
        else:
            self._quicksilver_url = '{}/services/bolt?az={}'.format(
                self._quicksilver_api_base_url, self._az_id
            )

        # Map of Bolt endpoints to use for connections, and mutex protecting it
        self._bolt_endpoints = defaultdict(list)
        self._mutex = Lock()

        self._get_endpoints()

        self._auth = BoltSigV4Auth(
            get_session().get_credentials().get_frozen_credentials(),
            "s3",
            region,
        )
        # Each client uses a random 4-char long prefix to randomize the S3 path used for auth lookups
        self._prefix = ''.join(
            random.choice(
                string.ascii_uppercase + string.ascii_lowercase + string.digits
            )
            for _ in range(4)
        )

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
        incoming_request = copy.deepcopy(prepared_request)
        _, _, path, query, fragment = urlsplit(prepared_request.url)
        host = self._select_endpoint(prepared_request.method)
        if self._scheme == "http":
            host = host + ":9000"

        prepared_request.url = urlunsplit(
            (self._scheme, host, path, query, fragment)
        )

        # TODO Fix handling requests without bucket names (like list)
        source_bucket = path.split('/')[1]

        # Construct the HEAD request that would be sent out by Bolt for authentication
        request = AWSRequest(
            method='HEAD',
            url='https://s3.{}.amazonaws.com/{}/{}/auth'.format(
                self._region, source_bucket, self._prefix
            ),
            data=None,
            params=None,
            headers=None,
        )
        # S3 requests always need the Content-SHA header included in the signature. As the HEAD request has no
        # content, it's just the SHA of an empty string and it's always the value below.
        # https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
        request.headers[
            'X-Amz-Content-Sha256'
        ] = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        self._auth.add_auth(request)

        for key in [
            "X-Amz-Date",
            "Authorization",
            "X-Amz-Security-Token",
            "X-Amz-Content-Sha256",
        ]:
            if request.headers.get(key):
                prepared_request.headers[key] = request.headers[key]
        prepared_request.headers['X-Bolt-Auth-Prefix'] = self._prefix

        try:
            bolt_response = BoltSession(self._hostname).send(prepared_request)
            if 400 <= bolt_response.status_code < 500:
                logger.debug(
                    "bolt request failed - 4xx - falling back to aws",
                    extra={"status_code": bolt_response.status_code},
                )
                return URLLib3Session().send(incoming_request)
            return bolt_response
        except Exception as e:
            logger.debug(
                "bolt request failed - exception - falling back to aws",
                extra={"exception": e},
            )
            return URLLib3Session().send(incoming_request)

    def _get_endpoints(self):
        try:
            response = http_pool.request('GET', self._quicksilver_url)
            if response.status == 200:
                response_data = response.data.decode('utf-8')
                endpoint_map = json.loads(response_data)
                with self._mutex:
                    self._bolt_endpoints = defaultdict(list, endpoint_map)
        except Exception as e:
            raise e

    def _select_endpoint(self, method):
        preferred_order = (
            self.PREFERRED_READ_ENDPOINT_ORDER
            if method in {"GET", "HEAD"}
            else self.PREFERRED_WRITE_ENDPOINT_ORDER
        )

        with self._mutex:
            for endpoints in preferred_order:
                if self._bolt_endpoints[endpoints]:
                    # use random choice for load balancing
                    return choice(self._bolt_endpoints[endpoints])
        # if we reach this point, no endpoints are available
        raise UnknownEndpointError(service_name='bolt', region_name=self._az_id)
