import type {Assessment} from "@smart-skin/shared";

export function filterAssessmentHistory(items:Assessment[],date:string|null,query=""):Assessment[]{
  const search=query.trim().toLowerCase();
  return items.filter(item=>{
    if(search&&!item.symptoms?.body_area.toLowerCase().includes(search)&&!item.symptoms?.description?.toLowerCase().includes(search))return false;
    if(!date)return true;
    const saved=Date.parse(item.created_at);
    return Number.isFinite(saved)&&new Date(saved+8*3600000).toISOString().slice(0,10)===date;
  });
}
