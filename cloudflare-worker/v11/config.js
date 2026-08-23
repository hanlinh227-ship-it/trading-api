export const V11_CONFIG=Object.freeze({
 version:'V11.4-v77v78-entry',
 mode:'SCALP',
 td:{creditsPerMinute:55,reserveLifecycle:5,reserveVerification:4,discoveryBudget:46},
 quoteTtlSec:{crypto:12,forex:35,metal:30,index:30},
 scanCadenceSec:{crypto:45,forex:75,metal:75,index:90},
 markets:{
  crypto:{quality:53,minRR:1.00,horizonMin:60,deepMax:10,scalpTargetAtr:1.00},
  forex:{quality:55,minRR:1.00,horizonMin:60,deepMax:8,scalpTargetAtr:.95},
  metal:{quality:56,minRR:1.03,horizonMin:60,deepMax:6,scalpTargetAtr:1.05},
  index:{quality:54,minRR:1.02,horizonMin:60,deepMax:7,scalpTargetAtr:1.00}
 }
});
export const V11_GROUPS=Object.freeze(['crypto','forex','metal','index']);
