// ---------------------------------------------------------------------------
// App-wide state for BatchMate using React Context + AsyncStorage persistence.
// This is the single source of truth the screens read from / write to.
// Swap the bodies of the async actions (login, sendMessage, rsvp, upgrade...)
// for real API/SDK calls when wiring a backend.
// ---------------------------------------------------------------------------
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { USERS, GROUPS, SEED_CHATS, REUNIONS, getUser } from './data';

const AppContext = createContext(null);
const STORE_KEY = 'batchmate.state.v1';

const initialState = {
  me: null, // current user object once registered
  friends: [], // array of user ids
  incoming: ['u8', 'u10'], // friend request ids (from -> me)
  outgoing: [], // ids I requested
  blocked: [],
  joinedGroups: ['g1'], // group ids
  chats: SEED_CHATS,
  rsvps: [], // reunion ids I'm attending
  premium: false,
  profileViewers: ['u4', 'u7', 'u2'], // who viewed me (premium feature)
  recentInstitutions: [], // recent institution searches (Step 3)
};

// --- Matching helpers (the "smart" part) -----------------------------------
// Score how related another user is to me, based on shared education + city.
export function matchScore(me, other) {
  if (!me) return { score: 0, reasons: [] };
  const reasons = [];
  let score = 0;
  for (const a of me.education || []) {
    for (const b of other.education || []) {
      if (a.name && a.name === b.name) {
        score += 3;
        if (a.batch === b.batch) {
          score += 4;
          reasons.push(`Batchmate • ${a.name} ${a.batch}`);
        } else {
          // Friendly short label: "College (UG)" -> "college".
          const lbl = (b.type || b.level || 'institution').replace(/\s*\(.*\)\s*/g, '').toLowerCase();
          reasons.push(`Same ${lbl} • ${a.name}`);
        }
        if (a.department && a.department === b.department) {
          score += 2;
          reasons.push(`Same dept • ${a.department}`);
        }
      }
    }
  }
  if (me.city && me.city === other.city) {
    score += 1;
    reasons.push(`Lives in ${other.city}`);
  }
  // De-duplicate reasons, keep most specific first.
  const seen = new Set();
  const uniq = reasons.filter((r) => (seen.has(r) ? false : seen.add(r)));
  return { score, reasons: uniq.slice(0, 2) };
}

export function AppProvider({ children }) {
  const [state, setState] = useState(initialState);
  const [hydrated, setHydrated] = useState(false);

  // Load persisted state on boot.
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORE_KEY);
        if (raw) setState((s) => ({ ...s, ...JSON.parse(raw) }));
      } catch (e) {
        // ignore corrupt cache
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  // Persist whenever state changes (after hydration).
  useEffect(() => {
    if (hydrated) AsyncStorage.setItem(STORE_KEY, JSON.stringify(state)).catch(() => {});
  }, [state, hydrated]);

  const actions = useMemo(() => ({
    // --- Auth / profile ---
    login: (profile) => setState((s) => ({ ...s, me: { id: 'me', ...profile } })),
    updateProfile: (patch) => setState((s) => ({ ...s, me: { ...s.me, ...patch } })),
    addEducation: (entry) =>
      setState((s) => ({ ...s, me: { ...s.me, education: [...(s.me.education || []), entry] } })),
    removeEducation: (index) =>
      setState((s) => ({ ...s, me: { ...s.me, education: (s.me.education || []).filter((_, i) => i !== index) } })),
    addRecentInstitution: (name) =>
      setState((s) => {
        const n = (name || '').trim();
        if (!n) return s;
        return { ...s, recentInstitutions: [n, ...s.recentInstitutions.filter((x) => x !== n)].slice(0, 8) };
      }),
    logout: () => setState({ ...initialState, me: null }),

    // --- Friend connections ---
    sendRequest: (id) =>
      setState((s) => (s.outgoing.includes(id) ? s : { ...s, outgoing: [...s.outgoing, id] })),
    cancelRequest: (id) => setState((s) => ({ ...s, outgoing: s.outgoing.filter((x) => x !== id) })),
    acceptRequest: (id) =>
      setState((s) => ({ ...s, incoming: s.incoming.filter((x) => x !== id), friends: [...s.friends, id] })),
    rejectRequest: (id) => setState((s) => ({ ...s, incoming: s.incoming.filter((x) => x !== id) })),
    removeFriend: (id) => setState((s) => ({ ...s, friends: s.friends.filter((x) => x !== id) })),
    block: (id) =>
      setState((s) => ({
        ...s,
        blocked: [...s.blocked, id],
        friends: s.friends.filter((x) => x !== id),
        incoming: s.incoming.filter((x) => x !== id),
        outgoing: s.outgoing.filter((x) => x !== id),
      })),
    unblock: (id) => setState((s) => ({ ...s, blocked: s.blocked.filter((x) => x !== id) })),

    // --- Groups ---
    joinGroup: (id) =>
      setState((s) => (s.joinedGroups.includes(id) ? s : { ...s, joinedGroups: [...s.joinedGroups, id] })),
    leaveGroup: (id) => setState((s) => ({ ...s, joinedGroups: s.joinedGroups.filter((x) => x !== id) })),

    // --- Messaging ---
    sendMessage: (chatId, text) =>
      setState((s) => ({
        ...s,
        chats: s.chats.map((c) =>
          c.id === chatId
            ? { ...c, messages: [...c.messages, { id: `m${Date.now()}`, from: 'me', text, at: Date.now() }] }
            : c
        ),
      })),
    startDM: (userId) => {
      let id;
      setState((s) => {
        const existing = s.chats.find((c) => c.type === 'dm' && c.with === userId);
        if (existing) {
          id = existing.id;
          return s;
        }
        id = `c${Date.now()}`;
        return { ...s, chats: [{ id, type: 'dm', with: userId, messages: [] }, ...s.chats] };
      });
      return id;
    },

    // --- Reunions ---
    toggleRsvp: (reunionId) =>
      setState((s) => ({
        ...s,
        rsvps: s.rsvps.includes(reunionId)
          ? s.rsvps.filter((x) => x !== reunionId)
          : [...s.rsvps, reunionId],
      })),

    // --- Premium ---
    upgrade: () => setState((s) => ({ ...s, premium: true })),
  }), []);

  // --- Derived selectors -----------------------------------------------------
  const selectors = useMemo(() => {
    const me = state.me;
    const visible = USERS.filter((u) => !state.blocked.includes(u.id));

    const ranked = visible
      .map((u) => ({ user: u, ...matchScore(me, u) }))
      .sort((a, b) => b.score - a.score);

    return {
      allUsers: visible,
      // People You May Know: high match score, not yet a friend / requested.
      suggestions: ranked.filter(
        (r) => r.score > 0 && !state.friends.includes(r.user.id) && !state.outgoing.includes(r.user.id)
      ),
      // Classmate matches grouped by reason category.
      batchmates: ranked.filter((r) => r.reasons.some((x) => x.startsWith('Batchmate'))),
      friendsList: state.friends.map(getUser).filter(Boolean),
      groups: GROUPS,
      joined: state.joinedGroups.map((id) => GROUPS.find((g) => g.id === id)).filter(Boolean),
      reunions: REUNIONS,
    };
  }, [state]);

  const value = { state, hydrated, ...actions, ...selectors };
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
