# Cloudwatch 2 Cloudwatch lambda

This lambda syncs a Cloudwatch log group with another account's Cloudwatch to allow querying the logs from central point.

## How it works
This solution uses a log group subscription to fire a lambda which connects to a central account and saves the logs in a log group named with source account's alias name (or ID if it is not set).

## Setting up
* Deploy the lambda with the code provided in [lambda_cw2cw.py](lambda_cw2cw.py)
* Set a resource-based permissions as in [policy_lambda_resource.json](policy_lambda_resource.json)
* Provide the lambda a role with permissions as defined in [policy_local_acct.json](policy_local_acct.json)
* On the target account, create another IAM role with permissions as defined in [policy_remote_acct.json](policy_remote_acct.json) and make a trust relationship with the account(s) the lambda runs on
* Set an env variable `AUDIT_ACCT_ROLE_ARN` for the lambda with ARN of the remote role
* Create a Lambda type subscription for the log group(s) you want to forward logs from and set the lambda as the target

## Careful 

This is asolution is not optimized for big workloads as it executes a lambda on every event in a log group. If you want to synchronize millions of log entries in multiple accounts this will impact your bills significantly.