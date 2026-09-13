from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class SceneResult:
    scene_id:int; status:str; attempts:int; seed:int; artifact_path:str|None; error:str|None

class SerialImageExecutor:
    def __init__(self,adapter,output_root): self.adapter=adapter; self.output_root=Path(output_root)
    def execute(self,job,workflow_factory,artifact_fetcher):
        self.output_root.mkdir(parents=True,exist_ok=True); results=[]
        for scene in job.scenes:
            accepted=None; last_error=None
            base_seed=100000+scene.id*1000
            for attempt in range(1,job.max_attempts+1):
                seed=base_seed+attempt-1
                try:
                    workflow=workflow_factory(job,scene,seed)
                    pid=self.adapter.submit(workflow); artifact=self.adapter.wait(pid)
                    target=self.output_root/f"scene_{scene.id:02d}.png"
                    artifact_fetcher(artifact,target)
                    accepted=SceneResult(scene.id,"ACCEPTED",attempt,seed,str(target),None); break
                except Exception as e: last_error=str(e)
            results.append(accepted or SceneResult(scene.id,"FAILED",job.max_attempts,base_seed+job.max_attempts-1,None,last_error))
        return tuple(results)
