import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {conditionInformation,getConditionInformation,conditionInformationCheckedOn,conditionInformationNotice} from "./conditionInformation.ts";
test("topics match the pinned eight-class model and preserve exact class IDs",()=>{
 const config=JSON.parse(readFileSync(new URL("../../../apps/api/disease_model.json",import.meta.url),"utf8"));const ids=conditionInformation.map(x=>x.id);
 assert.equal(ids.length,8);assert.equal(new Set(ids).size,8);assert.deepEqual(ids.slice().sort(),Object.keys(config.class_to_index).sort());assert.equal(getConditionInformation("seborrheic_dermatitis").label,"Seborrhoeic dermatitis");
});
test("unknown, prototype and simulation labels cannot silently select another topic",()=>{
 for(const id of ["unknown","toString","__proto__","Acne (example only)","ACNE","","eczema "])assert.equal(getConditionInformation(id),undefined);
});
test("cards contain sourced content and static public HTTPS links only",()=>{
 assert.equal(conditionInformationCheckedOn,"2026-10-29");assert.match(conditionInformationNotice,/does not confirm/);
 for(const item of conditionInformation){for(const text of [item.label,item.about,item.review,...item.signs])assert.ok(text.trim());assert.ok(item.signs.length&&item.sources.length);
 for(const s of item.sources){const u=new URL(s.url);assert.equal(u.protocol,"https:");assert.ok(["www.nhs.uk","dermnetnz.org","www.mayoclinic.org"].includes(u.hostname));assert.equal(u.search,"");assert.equal(u.hash,"");assert.ok(s.title.trim());}}
});
test("hives includes airway guidance and eczema does not identify a subtype",()=>{
 assert.match(getConditionInformation("urticaria").urgent,/emergency help immediately/);assert.match(getConditionInformation("urticaria").urgent,/breathing/);assert.match(getConditionInformation("eczema").about,/does not identify a subtype/);
});
