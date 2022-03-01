# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import json
from collections import defaultdict
from os import environ as _environ
from random import choice
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import urllib3
from boto3 import Session as _Session
from botocore.auth import SigV4Auth as _SigV4Auth
from botocore.awsrequest import AWSRequest as _AWSRequest
from botocore.config import Config as _Config
from botocore.exceptions import UnknownEndpointError


# Override Session Class
class Session(_Session):
    # URL of the quicksilver service discovery endpoint
    _service_url = None

    def client(self, *args, **kwargs):
        if kwargs.get('service_name') == 's3' or 's3' in args:
            kwargs['config'] = self._merge_bolt_config(kwargs.get('config'))

            if _environ.get('BOLT_URL') is not None:
                service_url = _environ.get('BOLT_URL')
            else:
                raise ValueError(
                    'Bolt URL could not be found.\nPlease expose env var BOLT_URL')

            if "{region}" in service_url:
                service_url = service_url.replace('{region}', self._get_region())
                
            self._service_url = service_url
            self._availability_zone_id = self._get_availability_zone_id()

            # refresh _bolt_endpoints
            self._get_bolt_endpoints()

            # Use inner function to curry 'creds' and 'bolt_url' into callback
            creds = self.get_credentials().get_frozen_credentials()

            def inject_header(*inject_args, **inject_kwargs):                
                # Modify request URL to redirect to bolt
                prepared_request = inject_kwargs['request']
                # using same scheme as service url for now
                scheme, _, _, _, _ = urlsplit(service_url)
                host = self._select_bolt_endpoint(prepared_request.method)
                _, _, path, query, fragment = urlsplit(prepared_request.url)
                prepared_request.url = urlunsplit((scheme, host, path, query, fragment))

                # Sign a get-caller-identity request
                request = _AWSRequest(
                    method='POST',
                    url='https://sts.amazonaws.com/',
                    data='Action=GetCallerIdentity&Version=2011-06-15',
                    params=None,
                    headers=None
                )
                _SigV4Auth(creds, "sts", 'us-east-1').add_auth(request)

                for key in ["X-Amz-Date", "Authorization", "X-Amz-Security-Token"]:
                    if request.headers.get(key):
                        prepared_request.headers[key] = request.headers[key]

            self.events.register_last('before-send.s3', inject_header)

            return self._session.create_client(*args, **kwargs)
        else:
            return self._session.create_client(*args, **kwargs)

    def _merge_bolt_config(self, client_config) :
        # Override client config
        bolt_config = _Config(
            s3={
                'addressing_style': 'path',
                'signature_version': 's3v4'
            }
        )
        if client_config is not None:
            return client_config.merge(bolt_config)
        else:
            return bolt_config

    def _get_region(self):
        region = self.region_name
        if region is not None:
            return region
        region = _environ.get('AWS_REGION')
        if region is not None:
            return region
        
        return self._default_get('http://169.254.169.254/latest/meta-data/placement/region')


    def _get_availability_zone_id(self):
        zone = _environ.get('AWS_ZONE_ID')
        if zone is not None:
            return zone
        
        return self._default_get('http://169.254.169.254/latest/meta-data/placement/availability-zone-id')

    def _get_bolt_endpoints(self):
        try:
            service_url = f'{self._service_url}/services/bolt?az={self._availability_zone_id}'
            resp = self._default_get(service_url)
            endpoint_map = json.loads(resp)
            self._bolt_endpoints = defaultdict(list, endpoint_map)
        except Exception as e:
            raise e

    def _select_bolt_endpoint(self, method):
        read_order = ["main_read_endpoints", "main_write_endpoints", "failover_read_endpoints", "failover_write_endpoints"]
        write_order = ["main_write_endpoints", "failover_write_endpoints"]
        preferred_order = read_order if method in {"GET", "HEAD"} else write_order
        for endpoints in preferred_order:
            if self._bolt_endpoints[endpoints]:
                # use random choice for load balancing
                return choice(self._bolt_endpoints[endpoints])
        # if we reach this point, no endpoints are available
        raise UnknownEndpointError(service_name='bolt', region_name=self._get_region())

    def _default_get(url):
        try:
            http = urllib3.PoolManager(timeout=3.0)
            resp = http.request('GET', url, retries=2)
            return resp.data.decode('utf-8')
        except Exception as e:
            raise e

# The default Boto3 session; autoloaded when needed.
DEFAULT_SESSION = None


def setup_default_session(**kwargs):
    """
    Set up a default session, passing through any parameters to the session
    constructor. There is no need to call this unless you wish to pass custom
    parameters, because a default session will be created for you.
    """
    global DEFAULT_SESSION
    DEFAULT_SESSION = Session(**kwargs)


def _get_default_session():
    """
    Get the default session, creating one if needed.

    :rtype: :py:class:`~boto3.session.Session`
    :return: The default session
    """
    if DEFAULT_SESSION is None:
        setup_default_session()

    return DEFAULT_SESSION


def client(*args, **kwargs):
    """
    Create a low-level service client by name using the default session.

    See :py:meth:`boto3.session.Session.client`.
    """
    return _get_default_session().client(*args, **kwargs)


def resource(*args, **kwargs):
    """
    Create a resource service client by name using the default session.

    See :py:meth:`boto3.session.Session.resource`.
    """
    return _get_default_session().resource(*args, **kwargs)


