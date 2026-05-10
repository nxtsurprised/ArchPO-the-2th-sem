# Ingress Validation

Run these commands from the repository root after installing Istio and deploying the traffic demo.

```sh
kubectl get pods -n istio-system -l app=istio-ingressgateway
kubectl get hpa -n istio-system
kubectl get pdb -n istio-system
kubectl get gateway,virtualservice -n traffic-demo
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
```

Expected local result:

- `istio-ingressgateway` has two replicas when the local machine has enough resources.
- `istio-ingressgateway` HPA has `MINPODS` set to 2 if you want the demo to keep two pods under low load.
- `istio-ingressgateway` PDB exists with `minAvailable: 1`.
- `curl` through `localhost:8080` returns HTTP 200 for `/api/demo`.

This validates the local API Gateway entrypoint. It does not prove production-grade high availability because Docker Desktop and k3d do not provide a real L2/VIP failover environment.
