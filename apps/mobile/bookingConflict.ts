import type {Booking,Slot} from "@smart-skin/shared";

export function conflictsWithVisit(slot:Pick<Slot,"starts_at"|"ends_at">,bookings:Booking[]):boolean{
  const start=Date.parse(slot.starts_at),end=Date.parse(slot.ends_at);
  return bookings.some(visit=>{
    if(visit.status!=="waiting"&&visit.status!=="called")return false;
    const visitStart=Date.parse(visit.starts_at);
    // Current API responses include ends_at; older cached visits used 30-minute slots.
    const visitEnd=visit.ends_at?Date.parse(visit.ends_at):visitStart+(visit.duration_minutes??30)*60000;
    return start<visitEnd&&visitStart<end;
  });
}
