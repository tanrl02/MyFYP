import type {Booking,Slot} from "@smart-skin/shared";
import {matchesBookingTime,type BookingTimePreference} from "./BookingTimeFilter";
import {conflictsWithVisit} from "./bookingConflict";

export function nextAvailableDate(slots:Slot[],bookings:Booking[],doctorIds:string[],time:BookingTimePreference,now=Date.now()):string|null{
  const doctors=new Set(doctorIds);
  // Keep the same duplicate-booking restriction as the Select time buttons.
  const booked=new Set(bookings.filter(visit=>visit.status!=="cancelled").map(visit=>visit.slot_id));
  let earliest:string|null=null;
  for(const slot of slots){
    if(!doctors.has(slot.doctor_id)||slot.available<=0||booked.has(slot.id)||!(Date.parse(slot.starts_at)>now)||!matchesBookingTime(slot,time)||conflictsWithVisit(slot,bookings))continue;
    if(earliest===null||slot.clinic_date<earliest)earliest=slot.clinic_date;
  }
  return earliest;
}
