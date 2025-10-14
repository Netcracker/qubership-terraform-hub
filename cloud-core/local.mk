# Configuration file for cloud-core-local-dev
# This file contains configurable values that can be overridden

# Installation configuration
# parameters used by script, but not propagated to helm values
CREATE_NAMESPACE ?= true
INSTALL_CRDS ?= true
INSTALL_METRICS_SERVER ?= true
INSTALL_MONITORING ?= false
INSTALL_CONSUL ?= false
INSTALL_DBAAS ?= false
# config file for dbaas installation - relative path will be resolved upon ./dbaas folder
DBAAS_CONFIG_FILE ?= local.mk
INSTALL_MAAS ?= false
# config file for maas installation - relative path will be resolved upon ./maas folder
MAAS_CONFIG_FILE ?= local.mk

# Namespace configuration
CORE_NAMESPACE ?= cloud-core
CONSUL_NAMESPACE ?= consul
MONITORING_NAMESPACE ?= monitoring
# pg & dbaas namespaces are propagated to dbaas-install
PG_NAMESPACE ?= pg
DBAAS_NAMESPACE ?= dbaas
# below namespaces are propagated to maas-install
MAAS_NAMESPACE ?= maas
RABBIT_NAMESPACE ?= rabbit
KAFKA_NAMESPACE ?= kafka

# General values
DEPLOYMENT_SESSION_ID ?= cloud-core-local-dev
MONITORING_ENABLED ?= false
CONSUL_SERVICE_NAME ?= consul-server
CONSUL_ENABLED ?= true

# DBaaS configuration
DBAAS_SERVICE_NAME ?= dbaas-aggregator

# MaaS configuration
KAFKA_INSTANCES ?= kafka-1
# empty value - skip rabbit installation
RABBIT_INSTANCES ?= 

# Core bootstrap configuration
CORE_BOOTSTRAP_IMAGE ?= ghcr.io/netcracker/core-bootstrap:latest 
CORE_CONFIG_CONSUL_ENABLED ?= false

# Components values
FACADE_OPERATOR_TAG ?= latest

INGRESS_GATEWAY_TAG ?= latest
INGRESS_GATEWAY_CLOUD_PUBLIC_HOST ?= svc.cluster.local
INGRESS_GATEWAY_CLOUD_PRIVATE_HOST ?= svc.cluster.local

CONTROL_PLANE_TAG ?= latest

PAAS_MEDIATION_TAG ?= latest

DBAAS_AGENT_TAG ?= latest

CORE_OPERATOR_TAG ?= latest
CORE_OPERATOR_IMAGE_REPOSITORY ?= ghcr.io/netcracker/qubership-core-core-operator

CONFIG_SERVER_TAG ?= latest
CONFIG_SERVER_IMAGE_REPOSITORY ?= ghcr.io/netcracker/qubership-core-config-server
CONFIG_SERVER_CONSUL_ENABLED ?= false

SITE_MANAGEMENT_TAG ?= latest
