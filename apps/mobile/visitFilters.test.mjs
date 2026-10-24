import test from "node:test";
import assert from "node:assert/strict";
import {filterVisits} from "./patientVisitFilter.ts";

const now=Date.parse("2032-10-23T01:00:00Z");
const token=visit=>`${visit.doctor_id==="doctor-lim"?"L":"A"}${String(visit.queue_number).padStart(3,"0")}`;
function fixture(){return [
  {id:"future",doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",queue_number:1,status:"waiting",starts_at:"2032-10-24T09:00:00+08:00",rescheduled_to_id:null},
  {id:"called",doctor_id:"doctor-anita",doctor_name:"Dr. Anita (demo)",queue_number:2,status:"called",starts_at:"2032-10-23T09:00:00+08:00",rescheduled_to_id:null},
  {id:"past",doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",queue_number:3,status:"waiting",starts_at:"2032-10-23T08:59:59+08:00",rescheduled_to_id:null},
  ...["completed","cancelled","missed"].map((status,i)=>({id:status,doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",queue_number:i+4,status,starts_at:"2032-10-24T09:00:00+08:00",rescheduled_to_id:null})),
  {id:"moved",doctor_id:"doctor-anita",doctor_name:"Dr. Anita (demo)",queue_number:7,status:"cancelled",starts_at:"2032-10-24T09:00:00+08:00",rescheduled_to_id:"replacement"}
];}
test("search matches the displayed doctor or queue token without case or surrounding-space sensitivity",()=>{
  const visits=fixture();
  assert.deepEqual(filterVisits(visits,"  aNiTa ","all",token,null,now).map(v=>v.id),["called","moved"]);
  assert.deepEqual(filterVisits(visits," l001 ","all",token,null,now).map(v=>v.id),["future"]);
  assert.equal(filterVisits(visits,"","all",token,null,now).length,7);
  assert.equal(filterVisits(visits,"nonexistent","all",token,null,now).length,0);
});
test("upcoming uses active status and normalised scheduled time with an inclusive boundary",()=>{
  assert.deepEqual(filterVisits(fixture(),"","upcoming",token,null,now).map(v=>v.id),["future","called"]);
  assert.deepEqual(filterVisits(fixture(),"","upcoming",token,null,now+1).map(v=>v.id),["future"]);
});
test("cancelled and rescheduled remain distinct; search combines with status",()=>{
  const visits=fixture();
  for(const status of ["completed","cancelled","missed"])assert.deepEqual(filterVisits(visits,"",status,token,null,now).map(v=>v.id),[status]);
  assert.deepEqual(filterVisits(visits,"anita","rescheduled",token,null,now).map(v=>v.id),["moved"]);
  assert.deepEqual(filterVisits(visits,"lim","rescheduled",token,null,now),[]);
});
test("filtering preserves original order and data, and follows refreshed status changes",()=>{
  const visits=fixture(),before=JSON.stringify(visits);
  filterVisits(visits,"lim","all",token,null,now);assert.equal(JSON.stringify(visits),before);
  const refreshed=visits.map(v=>v.id==="future"?{...v,status:"completed"}:v);
  assert.deepEqual(filterVisits(refreshed,"l001","upcoming",token,null,now),[]);
  assert.deepEqual(filterVisits(refreshed,"l001","completed",token,null,now).map(v=>v.id),["future"]);
  assert.deepEqual(filterVisits([],"","all",token,null,now),[]);
});

test("date uses the saved Malaysia clinic date, including UTC midnight boundaries",()=>{
  const visits=fixture().slice(0,3).map((v,i)=>({...v,clinic_date:i===0?"2032-10-24":"2032-10-23"}));
  visits[0].starts_at="2032-10-23T16:00:00Z";
  const before=JSON.stringify(visits);
  assert.deepEqual(filterVisits(visits,"","all",token,"2032-10-24",now).map(v=>v.id),["future"]);
  assert.deepEqual(filterVisits(visits,"","all",token,"2032-10-23",now).map(v=>v.id),["called","past"]);
  assert.deepEqual(filterVisits(visits,"","all",token,"2032-10-25",now),[]);
  assert.equal(filterVisits(visits,"","all",token,null,now).length,3);
  assert.equal(JSON.stringify(visits),before);
});

test("date combines with query/status and follows a refreshed appointment date",()=>{
  const visits=fixture().map(v=>({...v,clinic_date:"2032-10-24"}));
  assert.deepEqual(filterVisits(visits,"L001","upcoming",token,"2032-10-24",now).map(v=>v.id),["future"]);
  assert.deepEqual(filterVisits(visits,"anita","rescheduled",token,"2032-10-24",now).map(v=>v.id),["moved"]);
  assert.deepEqual(filterVisits(visits,"lim","completed",token,"2032-10-24",now).map(v=>v.id),["completed"]);
  const updated=visits.map(v=>v.id==="future"?{...v,clinic_date:"2032-10-25"}:v);
  assert.deepEqual(filterVisits(updated,"L001","upcoming",token,"2032-10-24",now),[]);
});
