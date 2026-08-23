export const V11_CONFIG=Object.freeze({
 version:'V11.2-symbol-scalp',
 mode:'SCALP',
 td:{creditsPerMinute:55,reserveLifecycle:5,reserveVerification:4,discoveryBudget:46},
 quoteTtlSec:{crypto:12,forex:35,metal:30,index:30},
 scanCadenceSec:{crypto:45,forex:75,metal:75,index:90},
 markets:{
  crypto:{quality:55,minRR:1.00,horizonMin:45,deepMax:10,scalpTargetAtr:.70},
  forex:{quality:58,minRR:1.05,horizonMin:60,deepMax:8,scalpTargetAtr:.65},
  metal:{quality:60,minRR:1.08,horizonMin:60,deepMax:6,scalpTargetAtr:.70},
  index:{quality:58,minRR:1.05,horizonMin:60,deepMax:7,scalpTargetAtr:.65}
 }
});
export const V11_GROUPS=Object.freeze(['crypto','forex','metal','index']);
