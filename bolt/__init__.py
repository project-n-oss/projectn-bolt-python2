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

import sys
from os import environ

from boto3 import Session as Boto3Session
from botocore.config import Config as BotoCoreConfig
from urlparse import urlsplit

from .bolt_router import BoltRouter, get_availability_zone_id, get_region

BOLT_ENDPOINT_UPDATE_INTERVAL = 10


# Override Session Class
class Session(Boto3Session):
    def __init__(self):
        super(Session, self).__init__()

        # Load all of the possibly configuration settings
        region = environ.get("BOLT_REGION")
        if region is None:
            try:
                region = get_region()
            except Exception as e:
                print(
                    "BOLT_REGION environment variable is not set, and could not be automatically determined."
                )
                sys.exit(1)

        custom_domain = environ.get("BOLT_CUSTOM_DOMAIN")
        service_url = environ.get("BOLT_URL")
        hostname = None

        if custom_domain is not None and region is not None:
            scheme = "https"
            service_url = "{}://quicksilver.{}.{}".format(scheme, region, custom_domain)
            hostname = "bolt.{}.{}".format(region, custom_domain)
        elif service_url is not None:
            scheme, service_url, _, _, _ = urlsplit(service_url)
            if "{region}" in service_url:
                if region is None:
                    raise ValueError(
                        "Bolt URL {} requires region to be specified".format(
                            service_url
                        )
                    )
                service_url = service_url.replace("{region}", region)
        else:
            # must define either `custom_domain` or `url`
            raise ValueError(
                "Bolt settings could not be found.\nPlease expose 1. BOLT_URL or 2. BOLT_CUSTOM_DOMAIN"
            )

        az_id = environ.get("BOLT_AZ_ID")
        if az_id is None:
            try:
                az_id = get_availability_zone_id()
            except Exception as e:
                pass

        self.bolt_router = BoltRouter(
            scheme=scheme,
            quicksilver_api_base_url=service_url,
            hostname=hostname,
            region=region,
            az_id=az_id,
            update_interval=BOLT_ENDPOINT_UPDATE_INTERVAL,
        )
        self.events.register_last("before-send.s3", self.bolt_router.send)

    def client(self, *args, **kwargs):
        if kwargs.get("service_name") == "s3" or "s3" in args:
            kwargs["config"] = self._merge_bolt_config(kwargs.get("config"))
            return self._session.create_client(*args, **kwargs)
        else:
            return self._session.create_client(*args, **kwargs)

    def _merge_bolt_config(self, client_config):
        # Override client config
        bolt_config = BotoCoreConfig(
            s3={"addressing_style": "path", "signature_version": "s3v4"}
        )
        if client_config is not None:
            return client_config.merge(bolt_config)
        else:
            return bolt_config


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
