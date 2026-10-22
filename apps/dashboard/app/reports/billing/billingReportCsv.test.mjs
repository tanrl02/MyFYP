import test from "node:test";
import assert from "node:assert/strict";
import {billingReportCsv} from "./billingReportCsv.ts";

const totals={invoice_count:3,paid_invoice_count:2,unpaid_invoice_count:1,billed_cents:3003,paid_cents:2002,unpaid_cents:1001};
function fixture(period="month"){
  return {period,start_date:"2032-02-01",end_date:"2032-02-29",timezone:"Asia/Kuala_Lumpur",generated_at:"2032-03-01T00:00:00+00:00",granularity:"day",billing:{...totals},buckets:[
    {start_date:"2032-02-01",end_date:"2032-02-01",billing:{...totals}},
    {start_date:"2032-02-02",end_date:"2032-02-02",billing:Object.fromEntries(Object.keys(totals).map(key=>[key,0]))}
  ]};
}
test("exports numeric MYR, invoice counts, period metadata and payment meaning",()=>{
  const csv=billingReportCsv(fixture());
  assert.ok(csv.startsWith("\uFEFF"));assert.ok(csv.endsWith("\r\n"));
  assert.equal(csv.split("\r\n").length,5);
  for(const text of ['"3","2","1","30.03","20.02","10.01"','"month","2032-02-01","2032-02-29"',
    '"2032-03-01T00:00:00+00:00"','"Asia/Kuala_Lumpur"','"Period total"','"Issue date"',
    'no money moves.','Invoice issue date','later simulated payments','not cash collected','not all clinic debt'])assert.ok(csv.includes(text),text);
  assert.ok(!csv.includes('"RM '));
});
test("retains zero rows and source data without rounding cents to whole MYR",()=>{
  const report=fixture(),before=JSON.stringify(report);
  const csv=billingReportCsv(report);
  assert.ok(csv.includes('"2032-02-02","2032-02-02","0","0","0","0.00","0.00","0.00"'));
  assert.equal(JSON.stringify(report),before);
});
test("quarter and year exports preserve issue month bounds and row order",()=>{
  for(const [period,end] of [["quarter","2032-03-31"],["year","2032-12-31"]]){
    const report=fixture(period);report.start_date="2032-01-01";report.end_date=end;report.granularity="month";
    report.buckets[0].start_date="2032-01-01";report.buckets[0].end_date="2032-01-31";
    const csv=billingReportCsv(report);
    assert.ok(csv.includes(`"${period}","2032-01-01","${end}"`));
    assert.ok(csv.includes('"Issue month","2032-01-01","2032-01-31"'));
    assert.ok(csv.indexOf('"Period total"')<csv.indexOf('"Issue month"'));
  }
});
test("quotes metadata and neutralises formula-like text",()=>{
  const report=fixture();report.timezone='Fictional, "示范"\r\nMalaysia';
  assert.ok(billingReportCsv(report).includes('"Fictional, ""示范""\r\nMalaysia"'));
  for(const text of ['=1+1','+SUM(A1)','-1+1','@SUM(A1)','  =1+1','\t=1+1']){
    report.timezone=text;assert.ok(billingReportCsv(report).includes(`"'${text}"`));
  }
});
