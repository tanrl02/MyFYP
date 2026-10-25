import type {Assessment} from "@smart-skin/shared";

export const assessmentOrderLabels={newest:"Newest first",oldest:"Oldest first"} as const;
export type AssessmentOrder=keyof typeof assessmentOrderLabels;
export const assessmentSourceLabels={all:"All sources",experimental_ai:"Experimental AI",simulation:"Simulation"} as const;
export type AssessmentSource=keyof typeof assessmentSourceLabels;

export function sortAssessmentHistory(items:Assessment[],order:AssessmentOrder):Assessment[]{
  return [...items].sort((a,b)=>{
    const left=Date.parse(a.created_at),right=Date.parse(b.created_at);
    if(Number.isFinite(left)!==Number.isFinite(right))return Number.isFinite(left)?-1:1;
    if(Number.isFinite(left)&&left!==right)return order==="oldest"?left-right:right-left;
    return a.id<b.id?-1:a.id>b.id?1:0;
  });
}

export function filterAssessmentHistory(items:Assessment[],date:string|null,query="",source:AssessmentSource="all"):Assessment[]{
  const search=query.trim().toLowerCase();
  return items.filter(item=>{
    if(source!=="all"&&item.origin!==source)return false;
    if(search&&!item.symptoms?.body_area.toLowerCase().includes(search)&&!item.symptoms?.description?.toLowerCase().includes(search))return false;
    if(!date)return true;
    const saved=Date.parse(item.created_at);
    return Number.isFinite(saved)&&new Date(saved+8*3600000).toISOString().slice(0,10)===date;
  });
}
