import json
from urllib.request import urlopen
from urllib.error import URLError

COMFY_URL="http://127.0.0.1:8188"

def run_preflight(timeout=5):
    result={"status":"BLOCKED","endpoint":COMFY_URL,"missing":[],"zero_paid_services":True}
    try:
        with urlopen(COMFY_URL+"/system_stats",timeout=timeout) as r:
            stats=json.loads(r.read().decode("utf-8"))
        with urlopen(COMFY_URL+"/object_info",timeout=timeout) as r:
            objects=json.loads(r.read().decode("utf-8"))
    except (URLError,OSError,ValueError) as e:
        result["missing"].append("ComfyUI API unavailable: "+str(e)); return result
    result["system_stats_available"]=bool(stats)
    required_base=["CheckpointLoaderSimple","CLIPTextEncode","EmptyLatentImage","KSampler","VAEDecode","SaveImage"]
    missing=[x for x in required_base if x not in objects]
    # Reference conditioning is mandatory: accept known local IPAdapter node families only.
    ref_nodes=[n for n in objects if "ipadapter" in n.lower()]
    if not ref_nodes: missing.append("IPAdapter reference-conditioning nodes")
    result["reference_nodes"]=sorted(ref_nodes)[:20]
    result["missing"].extend(missing)
    if not result["missing"]: result["status"]="READY"
    return result
