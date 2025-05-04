# Confirm boto3 is using s3v4 for generating URLs
#import boto3

#session = boto3.Session(profile_name='ThomasGeanLambdaAccess')
#s3 = session.client('s3')
#print("Signature version in use:", s3.meta.config.signature_version)


#Check AWS environemntal variables
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

def test_aws_credentials():
    try:
        session = boto3.Session()
        credentials = session.get_credentials().get_frozen_credentials()
        region = session.region_name or "Not set (falling back to us-east-1)"

        sts = session.client("sts")
        identity = sts.get_caller_identity()

        print("✅ AWS credentials loaded successfully.")
        print(f"Access Key ID     : {credentials.access_key}")
        print(f"Secret Access Key : {'*' * 8 + credentials.secret_key[-4:]}")
        print(f"Session Token     : {'(present)' if credentials.token else '(not using temporary creds)'}")
        print(f"Region            : {region}")
        print(f"Account ID        : {identity['Account']}")
        print(f"IAM ARN           : {identity['Arn']}")
        print(f"User ID           : {identity['UserId']}")

    except NoCredentialsError:
        print("❌ No AWS credentials found.")
    except PartialCredentialsError:
        print("❌ Incomplete AWS credentials found.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_aws_credentials()
