import json, time
from dataclasses import dataclass
from urllib.request import Request, urlopen
from urllib.error import URLError

class ComfyUIError(RuntimeError): pass
class DependencyMissing(ComfyUIError): pass

@dataclass(frozen=True)
class RenderArtifact:
    filename: str
    subfolder: str = ""
    type: str = "output"

class ComfyUIAdapter:
    def __init__(self, base_url="http://127.0.0.1:8188", timeout=10, max_polls=120, poll_seconds=1):
        if base_url != "http://127.0.0.1:8188": raise ValueError("ComfyUI endpoint must be local")
        self.base_url=base_url; self.timeout=timeout; self.max_polls=max_polls; self.poll_seconds=poll_seconds
    def _json(self,path,method="GET",body=None):
        data=None if body is None else json.dumps(body).encode()
        req=Request(self.base_url+path,data=data,method=method,headers={"Content-Type":"application/json"})
        try:
            with urlopen(req,timeout=self.timeout) as r: return json.loads(r.read().decode())
        except (URLError,OSError,ValueError) as e: raise ComfyUIError(str(e)) from e
    def preflight(self):
        stats=self._json("/system_stats"); objects=self._json("/object_info")
        required=["CheckpointLoaderSimple","CLIPTextEncode","EmptyLatentImage","KSampler","VAEDecode","SaveImage"]
        missing=[n for n in required if n not in objects]
        refs=[n for n in objects if "ipadapter" in n.lower()]
        if not refs: missing.append("IPAdapter reference-conditioning nodes")
        if missing: raise DependencyMissing(", ".join(missing))
        return {"stats":stats,"reference_nodes":refs}
    def submit(self,workflow):
        out=self._json("/prompt","POST",{"prompt":workflow})
        pid=out.get("prompt_id")
        if not pid: raise ComfyUIError("ComfyUI did not return prompt_id")
        return pid
    def wait(self,prompt_id):
        for _ in range(self.max_polls):
            hist=self._json("/history/"+prompt_id)
            rec=hist.get(prompt_id)
            if rec:
                status=rec.get("status",{})
                if status.get("status_str") == "error": raise ComfyUIError(str(status))
                for node in rec.get("outputs",{}).values():
                    imgs=node.get("images",[])
                    if imgs:
                        i=imgs[0]; return RenderArtifact(i["filename"],i.get("subfolder",""),i.get("type","output"))
            time.sleep(self.poll_seconds)
        raise ComfyUIError("ComfyUI render timed out")
