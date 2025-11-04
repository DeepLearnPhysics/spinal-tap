NAMESPACE ?= spinal-tap

run-apply:
	kubectl apply -k .

run-kustomize:
	kubectl kustomize .

dump: run-kustomize

apply: run-apply

delete:
	kubectl delete -k .
