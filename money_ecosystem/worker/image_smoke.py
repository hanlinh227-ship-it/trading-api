from .comfyui_adapter import ComfyUIAdapter, DependencyMissing

def smoke_preflight():
    adapter=ComfyUIAdapter()
    try:
        data=adapter.preflight()
        return {"status":"READY","reference_nodes":data["reference_nodes"],"zero_paid_services":True}
    except DependencyMissing as e:
        return {"status":"BLOCKED","missing":str(e),"zero_paid_services":True}
