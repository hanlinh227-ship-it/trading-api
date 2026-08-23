export const V11_CONFIG=Object.freeze({
 version:'V11.5-wide-scalp',
 mode:'SCALP',
 td:{creditsPerMinute:55,reserveLifecycle:5,reserveVerification:4,discoveryBudget:46},
 quoteTtlSec:{crypto:12,forex:35,metal:30,index:30},
 scanCadenceSec:{crypto:45,forex:75,metal:75,index:90},
 markets:{
  crypto:{quality:53,minRR:1.00,horizonMin:80,deepMax:10,scalpTargetAtr:1.40},
  forex:{quality:55,minRR:1.00,horizonMin:90,deepMax:8,scalpTargetAtr:1.30},
  metal:{quality:56,minRR:1.03,horizonMin:90,deepMax:6,scalpTargetAtr:1.50},
  index:{quality:54,minRR:1.02,horizonMin:90,deepMax:7,scalpTargetAtr:1.40}
 }
});
export const V11_GROUPS=Object.freeze(['crypto','forex','metal','index']);
