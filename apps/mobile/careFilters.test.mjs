import test from "node:test";
import assert from "node:assert/strict";
import {filterCare,sortCare,summarizeCare} from "./patientCareFilter.ts";

const record=(id,prescription=null,invoice=null)=>({visit:{id},prescription:prescription?{status:prescription,items:[]}:null,invoice:invoice?{status:invoice}:null});
test("care statuses distinguish issued prescriptions and actual invoice states",()=>{
  const records=[record("empty"),record("issued","issued"),record("issued-bill","issued","unpaid"),record("dispensed","dispensed"),record("unpaid","dispensed","unpaid"),record("paid","dispensed","paid"),record("bill-only",null,"unpaid")];
  const ids=status=>filterCare(records,status).map(r=>r.visit.id);
  assert.deepEqual(ids("all"),["issued","issued-bill","dispensed","unpaid","paid","bill-only"]);
  assert.deepEqual(ids("dispensing"),["issued","issued-bill"]);
  assert.deepEqual(ids("awaitingBill"),["issued","dispensed"]);
  assert.deepEqual(ids("unpaid"),["issued-bill","unpaid","bill-only"]);
  assert.deepEqual(ids("paid"),["paid"]);
});

test("awaiting bill combines with search/date and moves to unpaid when an invoice arrives",()=>{
  const records=[record("a","issued"),record("b","dispensed"),record("c","dispensed","unpaid"),record("d",null,"paid"),record("empty")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:i===0?"Dr. Lim":"Dr. Anita",token:i===0?"L001":"A001",clinic_date:i===1?"2032-10-24":"2032-10-23"}}));
  const token=v=>v.token;
  const before=JSON.stringify(records);
  assert.deepEqual(filterCare(records,"awaitingBill"," lim ",token,"2032-10-23").map(r=>r.visit.id),["a"]);
  assert.deepEqual(filterCare(records,"awaitingBill","a001",token,"2032-10-24").map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare(records,"awaitingBill","lim",token,"2032-10-24"),[]);
  assert.deepEqual(summarizeCare(filterCare(records,"awaitingBill")),{unpaidCents:0,paidCents:0,awaitingDispensing:1});
  assert.equal(JSON.stringify(records),before);
  const refreshed=records.map(r=>r.visit.id==="b"?{...r,invoice:{status:"unpaid",total_cents:3000}}:r);
  assert.deepEqual(filterCare(refreshed,"awaitingBill").map(r=>r.visit.id),["a"]);
  assert.deepEqual(filterCare(refreshed,"unpaid","anita",token,"2032-10-24").map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare([],"awaitingBill"),[]);
});
test("refresh transitions update membership without altering records or their order",()=>{
  const records=[record("a","issued"),record("b","dispensed","unpaid")];
  const before=JSON.stringify(records);
  filterCare(records,"unpaid"); assert.equal(JSON.stringify(records),before);
  const refreshed=[record("a","dispensed","unpaid"),record("b","dispensed","paid")];
  assert.deepEqual(filterCare(refreshed,"dispensing"),[]);
  assert.deepEqual(filterCare(refreshed,"unpaid").map(r=>r.visit.id),["a"]);
  assert.deepEqual(filterCare(refreshed,"paid").map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare([],"all"),[]);
});

test("search matches displayed doctor or token and combines with status without changing source",()=>{
  const records=[record("a","issued"),record("b","dispensed","paid"),record("c",null,"unpaid"),record("empty")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:i<2?"Dr. Lim (demo)":"Dr. Anita (demo)",token:i<2?"L001":"A002"}}));
  const token=visit=>visit.token;
  const before=JSON.stringify(records);
  const ids=(status,query)=>filterCare(records,status,query,token).map(r=>r.visit.id);
  assert.deepEqual(ids("all","  lIm  "),["a","b"]);
  assert.deepEqual(ids("paid"," l001 "),["b"]);
  assert.deepEqual(ids("dispensing","L001"),["a"]);
  assert.deepEqual(ids("unpaid","ANITA"),["c"]);
  assert.deepEqual(ids("paid","Anita"),[]);
  assert.deepEqual(ids("all","missing"),[]);
  assert.deepEqual(ids("all","   "),["a","b","c"]);
  assert.equal(JSON.stringify(records),before);
  const refreshed=records.map(r=>r.visit.id==="a"?{...r,visit:{...r.visit,doctor_name:"Dr. Other",token:"O003"}}:r);
  assert.deepEqual(filterCare(refreshed,"all","l001",token).map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare([],"all","lim",token),[]);
});

test("appointment date uses saved Malaysia clinic date and combines with search and status",()=>{
  const records=[record("a","dispensed","paid"),record("b","dispensed","paid"),record("c","issued"),record("empty")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:"Dr. Lim",token:"L001",clinic_date:i===1?"2032-10-23":"2032-10-24",starts_at:"2032-10-23T16:00:00Z"}}));
  const token=visit=>visit.token;
  const before=JSON.stringify(records);
  const ids=(status,query,date)=>filterCare(records,status,query,token,date).map(r=>r.visit.id);
  assert.deepEqual(ids("paid"," l001 ","2032-10-24"),["a"]);
  assert.deepEqual(ids("paid","LIM","2032-10-23"),["b"]);
  assert.deepEqual(ids("dispensing","lim","2032-10-24"),["c"]);
  assert.deepEqual(ids("all","","2032-10-25"),[]);
  assert.deepEqual(ids("paid","l001",null),["a","b"]);
  assert.deepEqual(ids("all","",null),["a","b","c"]);
  assert.equal(JSON.stringify(records),before);
  const refreshed=records.map(r=>r.visit.id==="a"?{...r,visit:{...r.visit,clinic_date:"2032-10-25"}}:r);
  assert.deepEqual(filterCare(refreshed,"paid","l001",token,"2032-10-24"),[]);
  assert.deepEqual(filterCare([],"all","",token,"2032-10-24"),[]);
});

test("care sorting uses appointment instants with deterministic ties and preserves source",()=>{
  const records=[
    ["late","2032-10-24T09:00:00+08:00",1],
    ["tie-b","2032-10-23T01:00:00Z",2],
    ["early","2032-10-22T09:00:00+08:00",1],
    ["tie-a","2032-10-23T09:00:00+08:00",2],
    ["tie-first","2032-10-23T09:00:00+08:00",1],
  ].map(([id,starts_at,queue_number])=>({...record(id,"dispensed","paid"),visit:{id,starts_at,queue_number}}));
  const before=JSON.stringify(records);
  assert.deepEqual(sortCare(records,"newest").map(r=>r.visit.id),["late","tie-first","tie-a","tie-b","early"]);
  assert.deepEqual(sortCare(records,"oldest").map(r=>r.visit.id),["early","tie-first","tie-a","tie-b","late"]);
  assert.equal(JSON.stringify(records),before);
  assert.deepEqual(sortCare([],"newest"),[]);
});

test("care sorting combines with all filters and follows refreshed appointment times",()=>{
  const records=[record("a","dispensed","paid"),record("b","dispensed","paid"),record("c",null,"unpaid")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:"Dr. Lim",token:"L001",clinic_date:"2032-10-24",queue_number:1,starts_at:`2032-10-24T${i===0?"10":"09"}:00:00+08:00`}}));
  const filtered=filterCare(records,"paid","lim",v=>v.token,"2032-10-24");
  assert.deepEqual(sortCare(filtered,"oldest").map(r=>r.visit.id),["b","a"]);
  assert.deepEqual(sortCare(filtered,"newest").map(r=>r.visit.id),["a","b"]);
  const refreshed=filtered.map(r=>r.visit.id==="a"?{...r,visit:{...r.visit,starts_at:"2032-10-24T08:00:00+08:00"}}:r);
  assert.deepEqual(sortCare(refreshed,"oldest").map(r=>r.visit.id),["a","b"]);
});

test("summary totals exact invoice cents, counts prescriptions once and excludes absent bills",()=>{
  const records=[record("a","issued"),record("b","issued","unpaid"),record("c","dispensed","paid"),record("d",null,"paid"),record("e","dispensed"),record("empty")];
  records[1].invoice.total_cents=1001;
  records[2].invoice.total_cents=2055;
  records[3].invoice.total_cents=0;
  records[0].prescription.items=[{},{}];
  const before=JSON.stringify(records);
  assert.deepEqual(summarizeCare(records),{unpaidCents:1001,paidCents:2055,awaitingDispensing:2});
  assert.equal(JSON.stringify(records),before);
  assert.deepEqual(summarizeCare([]),{unpaidCents:0,paidCents:0,awaitingDispensing:0});
  const refreshed=records.map(r=>r.visit.id==="b"?{...r,prescription:{status:"dispensed"},invoice:{...r.invoice,status:"paid"}}:r);
  assert.deepEqual(summarizeCare(refreshed),{unpaidCents:0,paidCents:3056,awaitingDispensing:1});
});

test("summary follows combined filters and is unaffected by sort order",()=>{
  const records=[record("a","issued"),record("b","dispensed","paid"),record("c",null,"unpaid")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:i===2?"Dr. Anita":"Dr. Lim",token:i===2?"A001":"L001",clinic_date:i===0?"2032-10-23":"2032-10-24",queue_number:1,starts_at:`2032-10-${i===0?"23":"24"}T09:00:00+08:00`},invoice:r.invoice?{...r.invoice,total_cents:i===1?1234:567}:null}));
  const shown=filterCare(records,"paid","lim",v=>v.token,"2032-10-24");
  const expected={unpaidCents:0,paidCents:1234,awaitingDispensing:0};
  assert.deepEqual(summarizeCare(shown),expected);
  for(const order of ["newest","oldest"])assert.deepEqual(summarizeCare(sortCare(shown,order)),expected);
  assert.deepEqual(summarizeCare(filterCare(records,"all","missing",v=>v.token)),{unpaidCents:0,paidCents:0,awaitingDispensing:0});
});


test("medicine search matches saved prescription names once per record without searching bill descriptions or directions",()=>{
  const records=[record("paid","dispensed","paid"),record("issued","issued"),record("bill-only",null,"unpaid"),record("empty")].map(r=>({...r,visit:{...r.visit,doctor_name:"Dr. Lim",token:"L001",clinic_date:"2032-10-24"}}));
  records[0].prescription.items=[{name:"Fictional catalogue cream",directions:"Use daily",strength:"1%",form:"Cream"},{name:"Other cream",directions:"Demo"}];
  records[1].prescription.items=[{name:"Fictional edited cream",directions:"Special directions"}];
  records[2].invoice.lines=[{description:"Fictional catalogue cream"}];
  const token=v=>v.token, before=JSON.stringify(records);
  const ids=query=>filterCare(records,"all",query,token).map(r=>r.visit.id);
  assert.deepEqual(ids("  CATALOGUE  "),["paid"]);
  assert.deepEqual(ids("cream"),["paid","issued"]);
  assert.deepEqual(ids("Special directions"),[]);
  assert.deepEqual(ids("1%"),[]);
  assert.deepEqual(ids("unrelated"),[]);
  assert.deepEqual(ids("lim"),["paid","issued","bill-only"]);
  assert.deepEqual(ids("l001"),["paid","issued","bill-only"]);
  assert.equal(JSON.stringify(records),before);
});

test("medicine search combines with status/date and refreshes from saved prescription data",()=>{
  const records=[record("a","dispensed","paid"),record("b","issued")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:"Dr. Lim",token:"L001",clinic_date:i===0?"2032-10-24":"2032-10-23"},prescription:{...r.prescription,items:[{name:"Saved cream"}]},invoice:r.invoice?{...r.invoice,total_cents:5500}:null}));
  const token=v=>v.token;
  assert.deepEqual(filterCare(records,"paid","CREAM",token,"2032-10-24").map(r=>r.visit.id),["a"]);
  assert.deepEqual(filterCare(records,"awaitingBill","cream",token,"2032-10-23").map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare(records,"paid","cream",token,"2032-10-23"),[]);
  assert.deepEqual(summarizeCare(filterCare(records,"paid","cream",token)),{unpaidCents:0,paidCents:5500,awaitingDispensing:0});
  const refreshed=records.map(r=>r.visit.id==="b"?{...r,prescription:{...r.prescription,items:[{name:"Other item"}]}}:r);
  assert.deepEqual(filterCare(refreshed,"all","cream",token).map(r=>r.visit.id),["a"]);
  assert.deepEqual(filterCare([],"all","cream",token),[]);
});
