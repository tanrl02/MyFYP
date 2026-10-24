import test from "node:test";
import assert from "node:assert/strict";
import { filterNotifications } from "./patientNotificationFilter.ts";

test("read filters partition loaded notifications while preserving data and server order",()=>{
  const items=[{id:"a",read_at:null},{id:"b",read_at:"2032-10-25T01:00:00Z"},{id:"c",read_at:null}];
  const before=JSON.stringify(items);
  assert.deepEqual(filterNotifications(items,"all").map(n=>n.id),["a","b","c"]);
  assert.deepEqual(filterNotifications(items,"unread").map(n=>n.id),["a","c"]);
  assert.deepEqual(filterNotifications(items,"read").map(n=>n.id),["b"]);
  assert.equal(JSON.stringify(items),before);
});

test("refreshed read status and incoming notifications update membership without marking anything read",()=>{
  const items=[{id:"a",read_at:null},{id:"b",read_at:"2032-10-25T01:00:00Z"}];
  const refreshed=[{id:"new",read_at:null},...items.map(n=>n.id==="a"?{...n,read_at:"2032-10-25T02:00:00Z"}:n)];
  assert.deepEqual(filterNotifications(refreshed,"unread").map(n=>n.id),["new"]);
  assert.deepEqual(filterNotifications(refreshed,"read").map(n=>n.id),["a","b"]);
  assert.equal(items[0].read_at,null);
  assert.deepEqual(filterNotifications([items[1]],"unread"),[]);
  assert.deepEqual(filterNotifications([items[0]],"read"),[]);
  for(const status of ["all","unread","read"])assert.deepEqual(filterNotifications([],status),[]);
});
