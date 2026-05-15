import boto3

from app.core.config import settings


def get_boto3_session():
    if settings.aws_profile:
        return boto3.Session(
            profile_name=settings.aws_profile,
            region_name=settings.aws_region,
        )

    return boto3.Session(region_name=settings.aws_region)


_session = get_boto3_session()

s3_client = _session.client("s3")
sqs_client = _session.client("sqs")
