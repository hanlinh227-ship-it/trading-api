from types import SimpleNamespace
from money_ecosystem.worker.image_render_executor import SerialImageExecutor

class FakeAdapter:
    def __init__(self): self.calls=[]
    def submit(self,w): self.calls.append(w["seed"]); return str(len(self.calls))
    def wait(self,p): return SimpleNamespace(filename="fake.png")

def test_serial_executor_uses_deterministic_scene_order(tmp_path):
    a=FakeAdapter(); e=SerialImageExecutor(a,tmp_path)
    job=SimpleNamespace(max_attempts=2,scenes=[SimpleNamespace(id=1),SimpleNamespace(id=2)])
    def wf(job,scene,seed): return {"seed":seed}
    def fetch(artifact,target): target.write_bytes(b"image")
    out=e.execute(job,wf,fetch)
    assert [x.scene_id for x in out]==[1,2]
    assert a.calls==[101000,102000]
    assert all(x.status=="ACCEPTED" for x in out)
