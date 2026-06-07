// ---------------------------------------------------------------------------
// Mock institution directory used by the Step 3 "Institution Search".
// In production replace with an API call (search by name + city). Each entry
// is { name, city }. The search always offers "Add Institution Manually" so
// anything not listed can still be entered.
// ---------------------------------------------------------------------------
export const INSTITUTIONS = [
  // Chennai
  { name: 'Anna University', city: 'Chennai' },
  { name: 'IIT Madras', city: 'Chennai' },
  { name: 'Loyola College', city: 'Chennai' },
  { name: 'Madras Christian College', city: 'Chennai' },
  { name: 'SRM Institute of Science and Technology', city: 'Chennai' },
  { name: 'Sathyabama Institute of Science and Technology', city: 'Chennai' },
  { name: 'St. Xavier\'s High School', city: 'Chennai' },
  { name: 'DAV Boys Senior Secondary School', city: 'Chennai' },
  { name: 'Government Polytechnic College', city: 'Chennai' },
  // Coimbatore
  { name: 'PSG College of Technology', city: 'Coimbatore' },
  { name: 'Coimbatore Institute of Technology', city: 'Coimbatore' },
  { name: 'Amrita Vishwa Vidyapeetham', city: 'Coimbatore' },
  { name: 'Bharathiar University', city: 'Coimbatore' },
  // Madurai
  { name: 'Madurai Kamaraj University', city: 'Madurai' },
  { name: 'Thiagarajar College of Engineering', city: 'Madurai' },
  // Tiruchirappalli
  { name: 'NIT Tiruchirappalli', city: 'Tiruchirappalli' },
  { name: 'Bharathidasan University', city: 'Tiruchirappalli' },
  // Bengaluru
  { name: 'Indian Institute of Science', city: 'Bengaluru' },
  { name: 'RV College of Engineering', city: 'Bengaluru' },
  { name: 'Bangalore University', city: 'Bengaluru' },
  { name: 'Christ University', city: 'Bengaluru' },
  { name: 'PES University', city: 'Bengaluru' },
  // Hyderabad
  { name: 'IIT Hyderabad', city: 'Hyderabad' },
  { name: 'Osmania University', city: 'Hyderabad' },
  { name: 'University of Hyderabad', city: 'Hyderabad' },
  // Mumbai
  { name: 'IIT Bombay', city: 'Mumbai' },
  { name: 'University of Mumbai', city: 'Mumbai' },
  { name: 'St. Xavier\'s College', city: 'Mumbai' },
  { name: 'Veermata Jijabai Technological Institute', city: 'Mumbai' },
  // Pune
  { name: 'Savitribai Phule Pune University', city: 'Pune' },
  { name: 'College of Engineering Pune', city: 'Pune' },
  // New Delhi / Delhi
  { name: 'IIT Delhi', city: 'New Delhi' },
  { name: 'University of Delhi', city: 'New Delhi' },
  { name: 'Jawaharlal Nehru University', city: 'New Delhi' },
  { name: 'Delhi Technological University', city: 'Delhi' },
  // Kochi / Thiruvananthapuram
  { name: 'Cochin University of Science and Technology', city: 'Kochi' },
  { name: 'University of Kerala', city: 'Thiruvananthapuram' },
  { name: 'College of Engineering Trivandrum', city: 'Thiruvananthapuram' },
  // Kolkata
  { name: 'University of Calcutta', city: 'Kolkata' },
  { name: 'Jadavpur University', city: 'Kolkata' },
  // Kanpur / Varanasi
  { name: 'IIT Kanpur', city: 'Kanpur' },
  { name: 'Banaras Hindu University', city: 'Varanasi' },
];

// Search by name (case-insensitive), prioritising the selected city.
export function searchInstitutions(query, city, limit = 10) {
  const q = (query || '').trim().toLowerCase();
  let list = INSTITUTIONS;
  if (q) list = list.filter((i) => i.name.toLowerCase().includes(q));
  list = [...list].sort((a, b) => (b.city === city ? 1 : 0) - (a.city === city ? 1 : 0));
  return list.slice(0, limit);
}

// Popular institutions in the selected city.
export function popularInCity(city, limit = 6) {
  return INSTITUTIONS.filter((i) => i.city === city).slice(0, limit);
}
