# kormikez @ 6jul2020
# Forward CloudWatch logs to another account (for audit purposes)
#
# This lambda needs: 
# - a local IAM role with permissions as defined in policy_local_acct.json 
# - an IAM role on the target audit account with permissions as defined in policy_remote_acct.json and a trust relationship with source account; the remote role ARN must be provided as env variable AUDIT_ACCT_ROLE_ARN

import base64
import boto3
import gzip
import json
import os

def lambda_handler(event, context):
    audit_acct_role_arn = os.environ['AUDIT_ACCT_ROLE_ARN']  
    aws_account_id = context.invoked_function_arn.split(":")[4]
    account_name = aws_account_id
    
    iam = boto3.client('iam')
    paginator = iam.get_paginator('list_account_aliases')
    for response in paginator.paginate():
        account_name=response['AccountAliases'][0]

    sts_connection = boto3.client('sts')
    audit_acct = sts_connection.assume_role(
        RoleArn=audit_acct_role_arn,
        RoleSessionName="audit_acct_role"
    )
    
    ACCESS_KEY = audit_acct['Credentials']['AccessKeyId']
    SECRET_KEY = audit_acct['Credentials']['SecretAccessKey']
    SESSION_TOKEN = audit_acct['Credentials']['SessionToken']

    client = boto3.client(
        'logs',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        aws_session_token=SESSION_TOKEN,
    )
    
    cw_data = event['awslogs']['data']
    compressed_payload = base64.b64decode(cw_data)
    uncompressed_payload = gzip.decompress(compressed_payload)
    payload = json.loads(uncompressed_payload)

    cw_loggroup=account_name
    if aws_account_id in payload['logStream']:
        cw_logstream = payload['logStream']
    else:
        cw_logstream = payload['logGroup']+"/"+payload['logStream']
    cw_message=str(payload['logEvents'][0]['message'])
    cw_timestamp=payload['logEvents'][0]['timestamp']
    
    try:
        response = client.create_log_group(
            logGroupName=cw_loggroup
        )
    except:
        pass
    try:
        response = client.create_log_stream(
            logGroupName=cw_loggroup,
            logStreamName=cw_logstream
        )
    except:
        pass
    
    response = client.describe_log_streams(
        logGroupName=cw_loggroup,
        logStreamNamePrefix=cw_logstream
    )
    
    if 'uploadSequenceToken' in response['logStreams'][0]:
        logstream_seq = response['logStreams'][0]['uploadSequenceToken']
        response = client.put_log_events(
            logGroupName=cw_loggroup,
            logStreamName=cw_logstream,
            logEvents=[
                {
                    'timestamp': cw_timestamp,
                    'message': cw_message
                },
            ],
            sequenceToken=logstream_seq
        )
        
    else:      
        response = client.put_log_events(
            logGroupName=cw_loggroup,
            logStreamName=cw_logstream,
            logEvents=[
                {
                    'timestamp': cw_timestamp,
                    'message': cw_message
                },
            ]
        )
