NAMESPACE ?= spinal-tap
KUBECTL_DEPLOY_CONTEXT ?= neutrino-ml
FLAVOR ?= larcv
KUSTOMIZE_DIR := overlays/$(FLAVOR)

ensure-flavor:
	@test -f "$(KUSTOMIZE_DIR)/kustomization.yaml" || \
		(echo "Unknown FLAVOR '$(FLAVOR)'; choose 'larcv' or 'lean'."; exit 1)

ensure-context:
	@CURRENT_CONTEXT=$$(kubectl config current-context); \
	if [ "$$CURRENT_CONTEXT" != "$(KUBECTL_DEPLOY_CONTEXT)" ]; then \
		echo "Configured deployment context incorrect; expecting $(KUBECTL_DEPLOY_CONTEXT), but got $$CURRENT_CONTEXT."; \
		exit 1; \
	fi

run-apply: ensure-flavor
	kubectl apply -k $(KUSTOMIZE_DIR)

run-kustomize: ensure-flavor
	kubectl kustomize $(KUSTOMIZE_DIR)

dump: run-kustomize

apply: ensure-context run-apply

delete: ensure-context ensure-flavor
	kubectl delete -k $(KUSTOMIZE_DIR)
