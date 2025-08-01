How to use:
1 Create following secrets:

AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
POSTGRESPASSWORD
POSTGRESUSER
REPLICATORPASSWORD
2 Create following variables:

AWS_REGION
TF_VAR_EKS_NEW_CLUSTERNAME
TF_VAR_PG_INSTALL_NAMESPACE

3 Run action with needed checkmarks selected

Improvements&plans:
rework tf state storage to bucket_name/cluster_name
change other components run logic to call different actions
include all infra components into checkbox
improve k8s installation tf steps to include ingress creation