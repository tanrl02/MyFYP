import type {Assessment} from "@smart-skin/shared";

export function filterAssessmentHistory(items:Assessment[],date:string|null):Assessment[]{
  if(!date)return [...items];
  return items.filter(item=>{
    const saved=Date.parse(item.created_at);
    return Number.isFinite(saved)&&new Date(saved+8*3600000).toISOString().slice(0,10)===date;
  });
}
