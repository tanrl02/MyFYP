import test from "node:test";
import assert from "node:assert/strict";
import {assessmentReportHtml,assessmentReportSignature,assessmentReportFilename,assessmentReportSections} from "./assessmentReport.ts";
const fixture=()=>({generated_at:"2026-10-29T08:00:00Z",scope:"patient",source_share_id:null,patient_name:'Ava <script>alert(1)</script>',assessment:{id:'safe-id',patient_id:'patient-ava',created_at:'2026-10-28T08:00:00Z',origin:'simulation',example_category:'Fictional',message:'No disease prediction',symptoms:{body_area:'Forearm 中文',onset:'3 days',itching:'yes',pain:'no',description:'<img src="https://example.com/private">'},photo_uri:'data:image/jpeg;base64,YQ=='},reviews:[]});
test('HTML escapes all user text and embeds only a JPEG data photo with no scripts or external requests',()=>{
 const f=fixture(),html=assessmentReportHtml(f);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img src="https:'));assert.ok(html.includes('img-src data:'));assert.ok(html.includes('Forearm 中文'));assert.ok(html.includes('data:image/jpeg;base64,YQ=='));
 for(const uri of ['https://example.com/photo','data:image/svg+xml,<svg onload=alert(1)>','data:image/jpeg;base64,YQ==" onerror="alert(1)']){f.assessment.photo_uri=uri;assert.ok(!assessmentReportHtml(f).includes('class="photo"'));}
});
test('simulation, patient symptoms and published reviews remain clearly separated',()=>{
 const f=fixture();assert.deepEqual(assessmentReportSections(f).map(s=>s.title),['Report details','Patient-reported symptoms','Simulation result','Published doctor reviews']);assert.match(assessmentReportHtml(f),/not a disease prediction/);
 f.assessment.origin='experimental_ai';f.assessment.prediction={created_at:'2026-10-28T08:00:00Z',model_id:'pinned-v1',top_predictions:[{label:'Eczema',score:.72}]};f.reviews=[{doctor_name:'Dr Lim',created_at:'2026-10-29T07:00:00Z',doctor_assessment:'Independent assessment',note:'Line 1\nLine 2',follow_up:'Fictional follow-up',access_revoked:true}];const html=assessmentReportHtml(f);assert.match(html,/Experimental AI results/);assert.match(html,/72.0%/);assert.match(html,/Historical review/);assert.match(html,/Independent assessment/);assert.match(html,/Line 1\nLine 2/);assert.match(html,/MYT/);
});
test('signature ignores generation time but detects changed content; filenames contain no identity/path injection',()=>{
 const f=fixture();assert.equal(assessmentReportSignature(f),assessmentReportSignature({...f,generated_at:'later'}));assert.notEqual(assessmentReportSignature(f),assessmentReportSignature({...f,patient_name:'Updated'}));f.assessment.id='../../evil <patient name>';assert.match(assessmentReportFilename(f),/^assessment-[a-zA-Z0-9-]+-\d+\.pdf$/);assert.ok(!assessmentReportFilename(f).includes('Ava'));
});
test('long multiline content remains complete and can wrap across printed pages',()=>{
 const f=fixture();f.assessment.symptoms.description='Long clinical context 中文\n'.repeat(150);const html=assessmentReportHtml(f);assert.equal(html.split('Long clinical context').length-1,150);assert.match(html,/overflow-wrap:anywhere/);assert.match(html,/@page\{size:A4/);assert.match(html,/white-space:pre-wrap/);
});
