import test from "node:test";
import assert from "node:assert/strict";
import { dailyReportCsv } from "./dailyReportCsv.ts";

function fixture() {
  return {clinic_date:"2026-10-12",timezone:"Asia/Kuala_Lumpur",generated_at:"2026-10-20T14:00:00+00:00",visits:{total:13,waiting:1,called:1,completed:6,cancelled:3,missed:0,rescheduled:2},visits_by_doctor:[{doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",visits:{total:4,waiting:1,called:1,completed:2,cancelled:0,missed:0,rescheduled:0}},{doctor_id:"doctor-anita",doctor_name:"Dr. Anita (demo)",visits:{total:9,waiting:0,called:0,completed:4,cancelled:3,missed:0,rescheduled:2}}],billing:{invoice_count:5,billed_cents:20400,paid_cents:20400,unpaid_cents:0},stock:{received_units:12,dispensed_units:9,lost_units:0,items:[{medicine_id:"demo-a",name:"Demo item A",received:7,dispensed:4,lost:0}]},feedback:{count:2,average_rating:4.5}};
}
test("exports report identity, date meanings and numeric MYR values",()=>{
  const csv=dailyReportCsv(fixture());
  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.endsWith("\r\n"));
  for(const value of ["2026-10-12","2026-10-20T14:00:00+00:00","Asia/Kuala_Lumpur","no money moves.","Appointment date","Activity date in Malaysia time","Submission date in Malaysia time"]) assert.ok(csv.includes(value),value);
  assert.ok(csv.includes('"Billed","","","204.00","MYR (simulated)"'));
  assert.ok(csv.includes('"Paid","","","204.00","MYR (simulated)"'));
  assert.ok(csv.includes('"Average rating","","","4.50","out of 5"'));
  assert.ok(csv.includes('"Stock items","Dispensed","demo-a","Demo item A","4","units"'));
});
test("preserves commas, quotes, Unicode and embedded line breaks",()=>{
  const report=fixture(); report.stock.items[0].name='Crème, "示范"\r\nLine two';
  assert.ok(dailyReportCsv(report).includes('"Crème, ""示范""\r\nLine two"'));
});
test("exports potentially executable catalogue text as text",()=>{
  for(const name of ['=1+1','+SUM(A1:A2)','-1+1','@SUM(A1:A2)','  =1+1','\t=1+1','\r=1+1']){
    const report=fixture(); report.stock.items[0].name=name;
    assert.ok(dailyReportCsv(report).includes(`"'${name}"`),JSON.stringify(name));
  }
});
test("empty feedback has blank average; zero values and source are preserved",()=>{
  const report=fixture(); report.feedback={count:0,average_rating:null}; report.stock.items=[];
  const original=JSON.stringify(report);
  const csv=dailyReportCsv(report);
  assert.ok(csv.includes('"Average rating","","","","out of 5"'));
  assert.ok(csv.includes('"Submitted ratings","","","0","ratings"'));
  assert.ok(csv.includes('"Unpaid","","","0.00","MYR (simulated)"'));
  assert.equal(JSON.stringify(report),original);
});

test("exports each doctor and keeps cancelled/rescheduled counts distinct",()=>{
  const csv=dailyReportCsv(fixture());
  assert.ok(csv.includes('"Visits by doctor","Booking records","doctor-lim","Dr. Lim (demo)","4","visits"'));
  assert.ok(csv.includes('"Visits by doctor","Cancelled","doctor-anita","Dr. Anita (demo)","3","visits"'));
  assert.ok(csv.includes('"Visits by doctor","Rescheduled","doctor-anita","Dr. Anita (demo)","2","visits"'));
  assert.ok(csv.includes('"Visits by doctor","Called","doctor-anita","Dr. Anita (demo)","0","visits"'));
});

test("exports missed appointments separately in clinic and doctor totals",()=>{
 const report=fixture(); report.visits.missed=1; report.visits.waiting=0; report.visits_by_doctor[0].visits.missed=1; report.visits_by_doctor[0].visits.waiting=0;
 const csv=dailyReportCsv(report);
 assert.ok(csv.includes('"Visits","Missed","","","1","visits"'));
 assert.ok(csv.includes('"Visits by doctor","Missed","doctor-lim","Dr. Lim (demo)","1","visits"'));
});
