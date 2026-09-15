export function detectWorkerConflicts(results=[]){
  const material=results.filter(r=>r&&r.verification_status==='conflict');
  return {hasConflict:material.length>0,materialCount:material.length,action:material.length?'checker_required':'merge_allowed',majorityVote:false};
}
