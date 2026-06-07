// ---------------------------------------------------------------------------
// Mock data layer for BatchMate.
// In production, replace these with API calls to your backend (users, search,
// chat, alumni, payments). The shapes below mirror the planned DB structure:
// Schools / Colleges / Universities / Polytechnics / Courses / Departments /
// Batches / Users / FriendConnections / Messages.
// ---------------------------------------------------------------------------

// Education levels supported by the app.
export const LEVELS = ['School', 'College', 'Polytechnic', 'University', 'Coaching Center'];

// --- Profile reference data -------------------------------------------------
// Basic-information option lists.
export const GENDERS = ['Male', 'Female', 'Other', 'Prefer not to say'];
export const MEDIUMS = ['English', 'Tamil', 'Hindi', 'Telugu', 'Malayalam', 'Kannada', 'Marathi', 'Other'];

// The education categories a user can add. Each drives its own field set
// (EDU_FIELDS) and predefined course/degree list (COURSE_OPTIONS).
export const EDUCATION_TYPES = [
  'School',
  'Diploma / Polytechnic',
  'College (UG)',
  'College (PG)',
  'University',
  'Professional Course',
  'Coaching Centre',
  'Certification / Training',
  'Other / Not Listed',
];

// Field descriptor helper.
//   kind: 'text' | 'number' | 'course' | 'medium'
//   'course' renders a picker from COURSE_OPTIONS[type] (free text if none).
const f = (key, label, opts = {}) => ({
  key,
  label,
  kind: opts.kind || 'text',
  required: !!opts.required,
});

// Shared field block reused by UG / PG / University degree records.
const DEGREE_FIELDS = (nameLabel) => [
  f('name', nameLabel),
  f('course', 'Degree', { kind: 'course' }),
  f('department', 'Department'),
  f('university', 'University'),
  f('batch', 'Batch Year', { kind: 'number' }),
  f('year', 'Year (e.g. Final Year)'),
  f('startYear', 'Start Year', { kind: 'number' }),
  f('endYear', 'Completion Year', { kind: 'number' }),
  f('city', 'City', { required: true }),
  f('district', 'District', { required: true }),
  f('state', 'State'),
];

// Which fields to show for each education type.
export const EDU_FIELDS = {
  'School': [
    f('name', 'School Name'),
    f('course', 'Class / Grade', { kind: 'course', required: true }),
    f('section', 'Section'),
    f('batch', 'Batch Year', { kind: 'number' }),
    f('medium', 'Medium', { kind: 'medium' }),
    f('city', 'City', { required: true }),
    f('district', 'District', { required: true }),
    f('state', 'State'),
  ],
  'Diploma / Polytechnic': [
    f('name', 'Institution Name'),
    f('course', 'Course', { kind: 'course' }),
    f('semester', 'Semester'),
    f('section', 'Section'),
    f('batch', 'Batch Year', { kind: 'number' }),
    f('medium', 'Medium', { kind: 'medium' }),
    f('city', 'City', { required: true }),
    f('district', 'District', { required: true }),
    f('state', 'State'),
  ],
  'College (UG)': DEGREE_FIELDS('College Name'),
  'College (PG)': DEGREE_FIELDS('College Name'),
  'University': DEGREE_FIELDS('University Name'),
  'Professional Course': [
    f('course', 'Professional Course', { kind: 'course' }),
    f('name', 'Institution / Academy Name', { required: true }),
    f('specialization', 'Specialization'),
    f('batch', 'Batch Year', { kind: 'number' }),
    f('startYear', 'Start Year', { kind: 'number' }),
    f('endYear', 'Completion Year', { kind: 'number' }),
    f('university', 'University'),
    f('year', 'Year'),
    f('city', 'City', { required: true }),
    f('district', 'District', { required: true }),
    f('state', 'State'),
  ],
  'Coaching Centre': [
    f('name', 'Coaching Name'),
    f('course', 'Course', { kind: 'course' }),
    f('year', 'Year', { kind: 'number' }),
  ],
  'Certification / Training': [
    f('name', 'Certification / Training Name'),
    f('course', 'Course', { kind: 'course' }),
    f('year', 'Year', { kind: 'number' }),
  ],
  'Other / Not Listed': [
    f('name', 'Institution Name'),
    f('course', 'Course / Title'),
    f('department', 'Department / Field'),
    f('batch', 'Batch Year', { kind: 'number' }),
    f('city', 'City'),
    f('state', 'State'),
  ],
};

// Predefined Course / Degree options per education type. An empty list means
// the "course" field falls back to free-text entry.
export const COURSE_OPTIONS = {
  'School': ['10th Standard (SSLC)', '12th Standard (HSC)', 'CBSE', 'ICSE', 'State Board', 'Other'],
  'Diploma / Polytechnic': [
    'Diploma in Mechanical Engineering', 'Diploma in Civil Engineering',
    'Diploma in Electrical Engineering', 'Diploma in Electronics',
    'Diploma in Computer Engineering', 'Diploma in Automobile Engineering',
    'Diploma in Agriculture', 'Other',
  ],
  'College (UG)': ['B.A.', 'B.Com.', 'B.Sc.', 'BCA', 'BBA', 'B.Tech / B.E.', 'B.Arch', 'B.Pharm', 'BSW', 'B.Ed', 'MBBS', 'BDS', 'B.Sc Nursing', 'Other'],
  'College (PG)': ['M.A.', 'M.Com.', 'M.Sc.', 'MBA', 'MCA', 'M.Tech / M.E.', 'M.Pharm', 'MSW', 'M.Ed', 'MD', 'MDS', 'Other'],
  'University': ['M.Phil', 'PhD', 'Doctorate', 'Post Doctoral Research', 'Other'],
  'Coaching Centre': ['UPSC', 'TNPSC', 'SSC', 'Banking', 'Railways', 'NEET', 'JEE', 'GATE', 'CAT', 'IELTS', 'TOEFL', 'Spoken English', 'Other'],
  'Certification / Training': ['Tally', 'AWS', 'Microsoft', 'Google Certification', 'Cisco CCNA', 'Red Hat', 'Python', 'Java', 'Data Science', 'Artificial Intelligence', 'Digital Marketing', 'Graphic Design', 'Web Development', 'Other'],
  'Professional Course': ['CA (Chartered Accountant)', 'CMA', 'CS (Company Secretary)', 'LLB', 'LLM', 'Nursing', 'Physiotherapy', 'Pharmacy', 'Aviation', 'Hotel Management', 'Fashion Design', 'Interior Design', 'Journalism', 'Animation', 'Other'],
  'Other / Not Listed': [],
};

// Build a one-line summary of an education record for compact display.
export function eduSummary(e) {
  return [e.course, e.specialization, e.department, e.batch || e.year]
    .filter(Boolean)
    .join(' • ');
}

// Build a location string from an education record.
export function eduLocation(e) {
  return [e.city, e.district, e.state].filter(Boolean).join(', ');
}

// Reference data (would come from institution tables).
export const INSTITUTIONS = [
  'ABC Engineering College',
  'Government Polytechnic Chennai',
  'St. Xavier\'s High School',
  'Anna University',
  'Delhi Public School',
  'National Institute of Technology',
  'City Coaching Center',
];
export const COURSES = ['B.Tech', 'B.E', 'Diploma', 'B.Sc', 'B.Com', 'M.Tech', 'MBA', 'SSLC', 'HSC'];
export const DEPARTMENTS = ['CSE', 'ECE', 'EEE', 'Mechanical', 'Civil', 'IT', 'Science', 'Commerce'];
export const BATCHES = ['2008', '2010', '2012', '2014', '2015', '2016', '2018', '2020', '2022'];

const edu = (level, name, course, department, batch, roll) => ({ level, name, course, department, batch, roll });

// People in the network (the current user is added at sign-up).
export const USERS = [
  {
    id: 'u1', name: 'Aarav Sharma', city: 'Chennai', state: 'Tamil Nadu',
    headline: 'Software Engineer @ Infosys', verified: true, isMentor: true,
    work: { title: 'Software Engineer', company: 'Infosys' },
    education: [
      edu('College', 'ABC Engineering College', 'B.Tech', 'ECE', '2015', 'EC15021'),
      edu('School', 'St. Xavier\'s High School', 'SSLC', 'Science', '2008'),
    ],
    where: 'Moved to Bangalore, leading a backend team.',
  },
  {
    id: 'u2', name: 'Priya Nair', city: 'Chennai', state: 'Tamil Nadu',
    headline: 'UX Designer', verified: true, isMentor: false,
    work: { title: 'Product Designer', company: 'Zoho' },
    education: [edu('College', 'ABC Engineering College', 'B.Tech', 'ECE', '2015', 'EC15044')],
    where: 'Freelancing and mentoring design students.',
  },
  {
    id: 'u3', name: 'Rohan Verma', city: 'Bengaluru', state: 'Karnataka',
    headline: 'Founder @ BuildRight', verified: false, isMentor: true,
    business: { name: 'BuildRight', category: 'Construction Tech' },
    work: { title: 'Founder', company: 'BuildRight' },
    education: [edu('College', 'ABC Engineering College', 'B.Tech', 'CSE', '2015', 'CS15003')],
    where: 'Running my own startup, hiring junior engineers.',
  },
  {
    id: 'u4', name: 'Sneha Iyer', city: 'Chennai', state: 'Tamil Nadu',
    headline: 'Data Analyst', verified: true, isMentor: false,
    work: { title: 'Data Analyst', company: 'TCS' },
    education: [edu('Polytechnic', 'Government Polytechnic Chennai', 'Diploma', 'ECE', '2012', 'DP12010')],
    where: 'Completed B.Tech via lateral entry, now in analytics.',
  },
  {
    id: 'u5', name: 'Karthik Raj', city: 'Coimbatore', state: 'Tamil Nadu',
    headline: 'Mechanical Engineer', verified: false, isMentor: false,
    work: { title: 'Design Engineer', company: 'Ashok Leyland' },
    education: [edu('Polytechnic', 'Government Polytechnic Chennai', 'Diploma', 'Mechanical', '2012', 'DP12077')],
    where: 'Working in automotive design in Hosur.',
  },
  {
    id: 'u6', name: 'Meera Krishnan', city: 'Chennai', state: 'Tamil Nadu',
    headline: 'Teacher', verified: true, isMentor: true,
    education: [edu('School', 'St. Xavier\'s High School', 'SSLC', 'Science', '2008')],
    where: 'Teaching mathematics at our old school!',
  },
  {
    id: 'u7', name: 'Aditya Kumar', city: 'Delhi', state: 'Delhi',
    headline: 'Marketing Lead', verified: false, isMentor: false,
    business: { name: 'GrowEasy', category: 'Digital Marketing' },
    education: [edu('University', 'Anna University', 'MBA', 'Commerce', '2018', 'MB18099')],
    where: 'Heading marketing for a D2C brand.',
  },
  {
    id: 'u8', name: 'Fatima Khan', city: 'Hyderabad', state: 'Telangana',
    headline: 'Civil Engineer', verified: true, isMentor: false,
    education: [edu('College', 'National Institute of Technology', 'B.Tech', 'Civil', '2016', 'CV16012')],
    where: 'Site engineer on metro projects.',
  },
  {
    id: 'u9', name: 'Vikram Singh', city: 'Chennai', state: 'Tamil Nadu',
    headline: 'Full-Stack Developer', verified: false, isMentor: true,
    work: { title: 'Tech Lead', company: 'Freshworks' },
    education: [edu('College', 'ABC Engineering College', 'B.Tech', 'CSE', '2015', 'CS15041')],
    where: 'Building SaaS products, happy to mentor.',
  },
  {
    id: 'u10', name: 'Divya Menon', city: 'Kochi', state: 'Kerala',
    headline: 'Doctor', verified: true, isMentor: false,
    education: [edu('School', 'Delhi Public School', 'HSC', 'Science', '2010')],
    where: 'Practicing medicine, settled in Kochi.',
  },
];

// Suggested batch groups.
export const GROUPS = [
  { id: 'g1', name: 'B.Tech ECE 2015', institution: 'ABC Engineering College', members: ['u1', 'u2', 'u3', 'u9'], color: '#4f46e5' },
  { id: 'g2', name: 'Polytechnic ECE 2012', institution: 'Government Polytechnic Chennai', members: ['u4', 'u5'], color: '#06b6d4' },
  { id: 'g3', name: 'School Batch 2008', institution: "St. Xavier's High School", members: ['u1', 'u6'], color: '#a855f7' },
  { id: 'g4', name: 'MBA 2018', institution: 'Anna University', members: ['u7'], color: '#f59e0b' },
];

// Alumni network content.
export const JOBS = [
  { id: 'j1', title: 'Backend Engineer', company: 'Infosys', location: 'Bengaluru', by: 'u1', type: 'Full-time' },
  { id: 'j2', title: 'UI/UX Designer', company: 'Zoho', location: 'Chennai', by: 'u2', type: 'Full-time' },
  { id: 'j3', title: 'Junior Developer (Freshers)', company: 'BuildRight', location: 'Remote', by: 'u3', type: 'Internship' },
];

export const MENTORS = ['u1', 'u3', 'u6', 'u9'];

export const BUSINESSES = [
  { id: 'b1', name: 'BuildRight', category: 'Construction Tech', by: 'u3', city: 'Bengaluru' },
  { id: 'b2', name: 'GrowEasy', category: 'Digital Marketing', by: 'u7', city: 'Delhi' },
];

export const REUNIONS = [
  {
    id: 'r1', title: 'ECE 2015 — 10 Year Reunion', group: 'g1',
    date: 'Dec 28, 2025', venue: 'Taj Coromandel, Chennai', fee: 1500,
    going: ['u1', 'u2'], host: 'u9',
    desc: 'A decade since we graduated! Dinner, awards and lots of nostalgia. Family welcome.',
  },
  {
    id: 'r2', title: 'School Batch 2008 Get-together', group: 'g3',
    date: 'Jan 12, 2026', venue: 'School Campus Grounds', fee: 500,
    going: ['u6'], host: 'u6',
    desc: 'Casual meetup at our old school. Tea, snacks and a campus tour.',
  },
];

// Pre-seeded conversations (with the current user, id "me").
export const SEED_CHATS = [
  {
    id: 'c1', type: 'dm', with: 'u2',
    messages: [
      { id: 'm1', from: 'u2', text: 'Hey! Is this really you from ECE 2015? 😄', at: Date.now() - 3600000 },
      { id: 'm2', from: 'me', text: 'Yes! Long time no see Priya!', at: Date.now() - 3500000 },
    ],
  },
  {
    id: 'cg1', type: 'group', groupId: 'g1',
    messages: [
      { id: 'm3', from: 'u9', text: 'Reunion planning thread — who is in? 🎉', at: Date.now() - 7200000 },
      { id: 'm4', from: 'u1', text: 'Count me in!', at: Date.now() - 7000000 },
    ],
  },
];

export const getUser = (id) => USERS.find((u) => u.id === id);
