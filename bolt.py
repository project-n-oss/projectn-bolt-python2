"""
Simple wrapper of boto3 client.
Bolt will do some special stuff in the background to ensure that:
- Signing is disabled
- Addressing style is == to path

- Implement a hook which intercepts request ()
    cli.register_last('before-send.s3', Bolt.send)
- Splits bolt url into parts
- adds custom header
    prepared_request.headers['X-Bolt-Identity-Request'] = get_session().create_client('sts').generate_presigned_url(
        'get_caller_identity', ExpiresIn=10)

Only intercepts for s3 commands.
Parse the BOLT url from the environment (or some other way) possibly KW args.
"""

from urllib.parse import urlsplit, urlunsplit

import boto3
from boto3 import Session
from botocore import UNSIGNED
from botocore.config import Config
from botocore.session import get_session
from botocore.handlers import disable_signing

import urllib.parse as urlparse
from urllib.parse import parse_qs

def _inject_header(*args, **kwargs):
  print('\n=======debug inject enter=========\n')
  bolt_url='https://bolt.turing-aws-gxxq.bolt.projectn.co'  # Remove Hardcoded Bolt URL
  scheme, host, _, _, _ = urlsplit(bolt_url)

  prepared_request = kwargs['request']
  print(prepared_request)
  _, _, path, query, fragment = urlsplit(prepared_request.url)
  prepared_request.url = urlunsplit((scheme, host, path, query, fragment))
  print('\n')
  print(prepared_request)

  # Sets the X-Bolt-Identity-Request header on the outbound request.
  # This will allow the Bolt service to proxy to AWS to resolve the caller's identity to check against ACLs.
  url = prepared_request.headers['X-Bolt-Identity-Request'] = Session(profile_name='nobolt').client('sts').generate_presigned_url(
      'get_caller_identity', ExpiresIn=10)

  print('\n')
  print(prepared_request)
  #TODO: avoid making sts calls each time in the same session

  print('\n=======inject exit=========\n')

def client(*args, **kwargs):
  # If client specifies 's3' service then intercept headers
  if kwargs.get('session_name') == 's3' or 's3' in args:
    session = Session(profile_name='bolt')
    session.events.register_last('before-send.s3', _inject_header)
    session.events.register(
      'choose-signer', disable_signing, unique_id='bolt-disable-signing')

    return session.client('s3', config=Config(signature_version=UNSIGNED)) # 'UNSIGNED' may be redundant

    # Modifies config if passed in by user. Else, adds config to kwargs
    '''
    config = kwargs.get('config')
    if config != None: 
      setattr(config, 'signature_version', UNSIGNED) 
    else:
      kwargs['config'] = Config(signature_version=UNSIGNED)
    return session.client(*args, **kwargs)
    '''
  else:
    return boto3.client(*args, **kwargs)

s3 = client('s3')
print(s3.list_buckets())

# TODO: Support session class creation...