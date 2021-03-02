import bolt as bolt3
import boto3


def client_tests():
    # Test signing for s3
    s3_boto = boto3.client('s3')
    s3_bolt = bolt3.client('s3')

    lboto = s3_boto.list_buckets()
    lbolt = s3_bolt.list_buckets()

    assert (lboto != lbolt)

    # Test that other services remain un-affected
    route_boto = boto3.client('route53')
    route_bolt = bolt3.client('route53')

    route_boto.get_account_limit(
        Type='MAX_HEALTH_CHECKS_BY_OWNER',
    )
    route_bolt.get_account_limit(
        Type='MAX_HEALTH_CHECKS_BY_OWNER',
    )


def session_tests():
    # Test signing for s3
    session_boto = boto3.Session(profile_name='nobolt')
    session_bolt = bolt3.Session(profile_name='nobolt')

    s3_boto = session_boto.client('s3')
    s3_bolt = session_bolt.client('s3')

    lboto = s3_boto.list_buckets()
    lbolt = s3_bolt.list_buckets()

    assert (lboto != lbolt)

    # Test that other services remain un-affected
    route_boto = session_boto.client('route53')
    route_bolt = session_bolt.client('route53')

    route_boto.get_account_limit(
        Type='MAX_HEALTH_CHECKS_BY_OWNER',
    )
    route_bolt.get_account_limit(
        Type='MAX_HEALTH_CHECKS_BY_OWNER',
    )


client_tests()
session_tests()
