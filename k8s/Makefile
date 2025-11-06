NAMESPACE ?= spinal-tap
KUBECTL_DEPLOY_CONTEXT ?= neutrino-ml

ensure-context:
	if [ "$(shell kubectl config current-context)" != "$(KUBECTL_DEPLOY_CONTEXT)" ]; then echo "Configured deployment context incorrect; expecting $(KUBECTL_DEPLOY_CONTEXT)."; exit 1; fi

run-apply:
	kubectl apply -k .

run-kustomize:
	kubectl kustomize .

dump: run-kustomize

apply: ensure-context run-apply

delete: ensure-context
	kubectl delete -k .
