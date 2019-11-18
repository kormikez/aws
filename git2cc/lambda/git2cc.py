# This lambda enables automatic synchronization of any external repo to CodeCommit.
# 
# Source repo needs to have a hook that triggers SNS event to which this lambda is subscribed.
#
# Required environment variables:
# - src_repo_user
# - src_repo_pass
#
# Optional environment variable:
# - LogLevel (if not set INFO level is assumed)
#

import boto3
import git
import json
import logging
import os
import re
import urllib
import time

def handler(event, context):

    # get the region and account ID
    global aws_region, aws_account_id
    aws_region = os.environ['AWS_DEFAULT_REGION']
    aws_account_id = context.invoked_function_arn.split(":")[4]

    # setup nice logging and set levels accordingly to env vars
    setup_logging(os.environ)

    # get the source repo details from event
    try:
        msg = event['Records'][0]['Sns']['Message']
        msg_parsed = json.loads(msg)
    except:
        raise Exception("Error parsing SNS message.")

    try:
        sr_url = msg_parsed['repository']['git_http_url']
        sr_name = msg_parsed['repository']['name']
        sr_branch = msg_parsed['ref'].split('/', 2)[2]
        logger.info("Source repo: " + sr_url)
    except:
        raise Exception("Unable to get source repository URL.")

    # get credentials (sr_ for source repo, cc_ for CodeCommit)
    sr_user, sr_pass, cc_user, cc_pass = get_credentials()

    # prepare local temp directory to store repository
    local_repo_path = '/tmp/' + context.aws_request_id + '/'

    # pull the external repo
    pull_source_repo (sr_name, sr_url, sr_branch, sr_user, sr_pass, local_repo_path)

    # push the repo to CodeCommit
    status = push_to_cc (sr_name, sr_branch, cc_user, cc_pass, sr_url, local_repo_path)

    # check the status and put a message accordingly
    if status:
        return 'Unable to sync repository '+sr_url+' (branch '+ sr_branch +') to CodeCommit.'
    else:
        return 'Successfully synced repository '+sr_url+' (branch '+ sr_branch +') to CodeCommit.'


# some neat logging instead of raw printing
def setup_logging(env):
    global logger
    logging.basicConfig()
    logger = logging.getLogger('git2cc')
    if "LogLevel" in env:
        env_level = env["LogLevel"]
    else:
        env_level = 'INFO'

    if env_level in ['CRITICAL', 'WARNING', 'INFO', 'DEBUG']:
        level = logging.getLevelName(env_level)
        logger.setLevel(level)
        git.LOGGER.setLevel(level)
    else:
        logger.setLevel(logging.INFO)
        git.LOGGER.setLevel(logging.INFO)


# git pull
def pull_source_repo(repo_name, repo_url, branch, user, pwd, path):
    
    auth_repo_url = re.sub('//', '//'+user+':'+pwd+'@', repo_url)
    os.mkdir(path)
    try:
        git.exec_command('clone', '--single-branch', '-b', branch, auth_repo_url, cwd=path)
    except Exception:
        raise(Exception)


# git push, including temporary git user in AWS IAM
def push_to_cc(repo_name, branch, cc_user, cc_pass, sr_url, path):

    cc = boto3.client('codecommit')
    try:
        cc.create_repository(
            repositoryName = repo_name,
            repositoryDescription = 'Sync\'d from ' + sr_url
            )
    except Exception as e:
        if "RepositoryNameExistsException" in str(e):
            logger.info("Repository " + repo_name + " already exists in CodeCommit.")
        else:
            return 1

    codecommit_repo_url = 'https://' + cc_user + ':' + cc_pass + '@git-codecommit.' + aws_region + '.amazonaws.com/v1/repos/' + repo_name

    git.exec_command('remote', 'add', 'codecommit', codecommit_repo_url , cwd=path+'/'+repo_name)
    git.exec_command('push', 'codecommit', branch, cwd=path+'/'+repo_name)

    return 0

# get external repo username (directly from ENV) and passwords (from S3)
def get_credentials():
    try:
        sr_user = os.environ['src_repo_user']
        sr_pass = os.environ['src_repo_pass']

    except:
        raise Exception("Looks like env variables for the function are not set.")

    try:
        ssm_client = boto3.client('ssm')
        cc_user_obj = ssm_client.get_parameter(Name='git2ccLambdaUser')
        cc_user = urllib.parse.quote_plus(cc_user_obj['Parameter']['Value'])
        cc_pass_obj = ssm_client.get_parameter(Name='git2ccLambdaPwd',WithDecryption=True)
        cc_pass = urllib.parse.quote_plus(cc_pass_obj['Parameter']['Value'])
    except:
        raise Exception("Unable to get CodeCommit credentials from SSM.")

    return (sr_user, sr_pass, cc_user, cc_pass)
