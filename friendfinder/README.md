# BatchMate — Alumni / Classmate Finder App

Cross-platform (Android · iOS · Web) app to **reconnect with old classmates** from
school, college, polytechnic and university — built with **React Native + Expo
(Expo Router)** from a single codebase.

> This is a complete, runnable front-end with a local mock-data layer and
> persistent state, so every flow works end-to-end. Backend services
> (SMS-OTP, real chat server, payments, AI face-matching) are stubbed and
> clearly marked — swap them for real APIs when you're ready.

## Features implemented

**Core reconnect flow**
- Onboarding: mobile-OTP / email / Google login (mocked), profile creation, multi-entry education history
- Rich profile settings:
  - **Basic Information** — full name, nickname, profile photo, gender, date of birth, mobile & email (each with a privacy "hide" toggle), city/state
  - **Education Details** — add multiple records across **School · Diploma / Polytechnic · College (UG) · College (PG) · University · Professional Course · Coaching Centre · Certification / Training · Other**. Each type shows its own fields (Class/Grade, Semester, Department, Batch Year, Start/Completion Year, Medium, City/District/State…) with required-field validation
  - **Predefined Course / Degree options** per education type (e.g. SSLC/HSC for School, B.Tech/MBBS for UG, MBA/MCA for PG, PhD for University, UPSC/NEET/GATE for Coaching, AWS/Python for Certification, CA/LLB for Professional Course) — with an "Other" free-text fallback
  - **Edit Profile** screen to update basic info and add / remove education records any time
- Smart Search — free-text + batch/department filters (e.g. `ABC College 2015 ECE`)
- Classmate matching with a relevance score (batchmate / same dept / same college / same city)
- Friend requests: send, accept, reject, cancel, block

**Messaging**
- Private & group chat threads, composer with media (+) and voice-note buttons
- Conversation list with last message & time

**Batch groups & alumni**
- Batch groups (join / leave / member list / group chat)
- Alumni network: Jobs, Mentorship, Business directory, Reunions, Groups
- Reunion planning: event detail, attendees, RSVP + pay (mock)

**Premium + AI**
- "People You May Know" AI suggestions (match algorithm in `src/store.js`)
- "Who viewed your profile" (locked behind Premium)
- Premium upgrade screen (₹99/month, mock billing)
- Profile verification badge

## Tech

- **Expo SDK 51**, React Native 0.74, **Expo Router** (file-based routing)
- `@react-native-async-storage/async-storage` for persistence
- `@expo/vector-icons` (Ionicons)
- Works on **iOS, Android and Web** from the same code

## Project structure

```
app/                       # Expo Router routes
  _layout.js               # providers + root stack
  index.js                 # auth redirect
  (auth)/                  # welcome, login, otp, register, education
  (tabs)/                  # home, search, chats, alumni, profile
  user/[id].js             # other user's profile
  chat/[id].js             # chat thread (dm + group)
  group/[id].js            # batch group detail
  reunion/[id].js          # reunion detail + RSVP
  premium.js               # premium upgrade (modal)
src/
  theme.js                 # design tokens, avatar colors
  data.js                  # mock data (users, groups, jobs, reunions…)
  store.js                 # Context state + matching logic + persistence
  components/ui.js         # reusable UI (Avatar, Button, Card, Tag, Field…)
```

## Run it

```bash
cd friendfinder
npm install          # or: npx expo install
npx expo start       # press i (iOS), a (Android), or w (Web)
```

- **Web:** `npm run web`
- **iOS:** `npm run ios` (Mac + Xcode)  ·  or scan the QR with Expo Go
- **Android:** `npm run android`  ·  or scan the QR with Expo Go

Demo login: enter any mobile/email, then **any 4-digit OTP** to proceed.

## Wiring a real backend (next steps)

| Area | Replace mock in… | Suggested service |
|------|------------------|-------------------|
| OTP login | `app/(auth)/otp.js`, `login.js` | MSG91 / Twilio / Firebase Auth |
| Google login | `app/(auth)/login.js` | `expo-auth-session` / Firebase |
| Users / search / friends | `src/store.js`, `src/data.js` | REST/GraphQL API + Postgres |
| Chat | `app/chat/[id].js`, `src/store.js` | Firebase / Stream / Socket.io |
| Payments (premium, reunions) | `app/premium.js`, `reunion/[id].js` | Razorpay / Play & App Store billing |
| AI (PYMK, face match) | `matchScore()` in `src/store.js` | Your ML service / vector search |

## Database structure (target)

Schools · Colleges · Universities · Polytechnic Institutes · Courses ·
Departments · Batches · Users · FriendConnections · Messages — mirrored by the
shapes in `src/data.js`.
