import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Tag, Button, SectionTitle } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp } from '../../src/store';
import { getUser, eduSummary, eduLocation } from '../../src/data';

// One labelled row inside the Basic Information card.
function InfoRow({ icon, label, value, hidden }) {
  if (!value) return null;
  return (
    <View style={styles.infoRow}>
      <Ionicons name={icon} size={18} color={colors.muted} style={{ marginRight: 12 }} />
      <View style={{ flex: 1 }}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={styles.infoValue}>{value}</Text>
      </View>
      {hidden ? (
        <View style={styles.hiddenPill}>
          <Ionicons name="eye-off" size={12} color={colors.muted} />
          <Text style={styles.hiddenText}>Hidden</Text>
        </View>
      ) : null}
    </View>
  );
}

export default function Profile() {
  const router = useRouter();
  const { state, friendsList, logout } = useApp();
  const me = state.me;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScrollView contentContainerStyle={{ paddingBottom: 28 }} showsVerticalScrollIndicator={false}>
        {/* Header card */}
        <View style={styles.cover}>
          <Pressable style={styles.gear} onPress={logout}>
            <Ionicons name="log-out-outline" size={20} color="#fff" />
          </Pressable>
        </View>
        <View style={styles.profileTop}>
          <Avatar name={me?.name} size={92} />
          <Text style={styles.name}>{me?.name}{me?.nickname ? <Text style={styles.nickname}>  “{me.nickname}”</Text> : null}</Text>
          <Text style={styles.headline}>{me?.headline}</Text>
          <Text style={styles.loc}><Ionicons name="location" size={13} color={colors.muted} /> {[me?.city, me?.state].filter(Boolean).join(', ')}</Text>

          <View style={styles.statsRow}>
            <View style={styles.stat}><Text style={styles.statNum}>{friendsList.length}</Text><Text style={styles.statLabel}>Connections</Text></View>
            <View style={styles.divider} />
            <View style={styles.stat}><Text style={styles.statNum}>{me?.education?.length || 0}</Text><Text style={styles.statLabel}>Education</Text></View>
            <View style={styles.divider} />
            <View style={styles.stat}><Text style={styles.statNum}>{state.joinedGroups.length}</Text><Text style={styles.statLabel}>Groups</Text></View>
          </View>
        </View>

        <View style={styles.body}>
          {/* Basic Information */}
          <SectionTitle action="Edit" onAction={() => router.push('/edit-profile')}>Basic Information</SectionTitle>
          <Card>
            <InfoRow icon="happy-outline" label="Nickname" value={me?.nickname} />
            <InfoRow icon="male-female-outline" label="Gender" value={me?.gender} />
            <InfoRow icon="calendar-outline" label="Date of Birth" value={me?.dob} />
            <InfoRow icon="call-outline" label="Mobile Number" value={me?.mobile} hidden={me?.mobileHidden} />
            <InfoRow icon="mail-outline" label="Email ID" value={me?.email} hidden={me?.emailHidden} />
            <InfoRow icon="location-outline" label="Location" value={[me?.city, me?.state].filter(Boolean).join(', ')} />
            {!me?.nickname && !me?.gender && !me?.dob && !me?.mobile && !me?.email && (
              <Text style={styles.meta}>Tap Edit to add your details.</Text>
            )}
          </Card>

          {/* Verification */}
          <Card style={styles.verifyCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Ionicons name={me?.verified ? 'shield-checkmark' : 'shield-outline'} size={26} color={me?.verified ? colors.success : colors.warning} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{me?.verified ? 'Verified Profile' : 'Get Verified'}</Text>
                <Text style={styles.meta}>{me?.verified ? 'Your batch & ID are confirmed.' : 'Verify college email or student ID to build trust.'}</Text>
              </View>
            </View>
            {!me?.verified && <Button small title="Verify Now" variant="soft" icon="mail" style={{ marginTop: 12, alignSelf: 'flex-start' }} />}
          </Card>

          {/* Premium */}
          <Pressable onPress={() => router.push('/premium')} style={styles.premiumCard}>
            <View style={{ flex: 1 }}>
              <Text style={styles.premiumTitle}>{state.premium ? '⭐ Premium Active' : 'Upgrade to Premium'}</Text>
              <Text style={styles.premiumSub}>{state.premium ? 'You have unlimited access.' : 'See who viewed you, unlimited chats & filters.'}</Text>
            </View>
            <Ionicons name="chevron-forward" size={22} color="#fff" />
          </Pressable>

          {/* Who viewed me (premium) */}
          <SectionTitle>Who Viewed Your Profile</SectionTitle>
          <Card>
            {state.profileViewers.slice(0, 3).map((id, i) => {
              const u = getUser(id);
              const locked = !state.premium;
              return (
                <View key={id} style={[styles.viewerRow, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
                  <View style={locked ? { opacity: 1 } : null}>
                    <Avatar name={locked ? '? ?' : u?.name} size={42} />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={[styles.cardTitle, { fontSize: 15 }, locked && styles.blur]}>{locked ? '••••••••' : u?.name}</Text>
                    <Text style={styles.meta}>{locked ? 'Upgrade to reveal' : u?.headline}</Text>
                  </View>
                  {locked ? <Ionicons name="lock-closed" size={18} color={colors.gold} /> : <Ionicons name="chevron-forward" size={18} color={colors.muted} />}
                </View>
              );
            })}
          </Card>

          {/* Education */}
          <SectionTitle action="Add / Edit" onAction={() => router.push('/edit-profile')}>Education History</SectionTitle>
          {(me?.education || []).map((e, i) => (
            <Card key={i} style={{ marginBottom: 10, flexDirection: 'row', alignItems: 'flex-start' }}>
              <View style={styles.eduIcon}><Ionicons name="school" size={20} color={colors.primary} /></View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{e.name || e.course || e.type}</Text>
                {!!eduSummary(e) && <Text style={styles.meta}>{eduSummary(e)}</Text>}
                {!!e.university && <Text style={styles.meta}>{e.university}</Text>}
                {!!eduLocation(e) && <Text style={styles.meta}>{eduLocation(e)}</Text>}
                <Tag label={e.type || e.level} />
              </View>
            </Card>
          ))}
          {(!me?.education || me.education.length === 0) && (
            <Card><Text style={styles.meta}>No education added yet.</Text></Card>
          )}

          {/* Menu */}
          <SectionTitle>Settings</SectionTitle>
          {[
            ['create-outline', 'Edit Profile', () => router.push('/edit-profile')],
            ['shield-checkmark-outline', 'Verification'],
            ['notifications-outline', 'Notifications'],
            ['lock-closed-outline', 'Privacy & Blocked Users'],
            ['help-circle-outline', 'Help & Support'],
          ].map(([icon, label, onPress]) => (
            <Pressable key={label} style={styles.menuRow} onPress={onPress}>
              <Ionicons name={icon} size={20} color={colors.body} />
              <Text style={styles.menuText}>{label}</Text>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
          ))}

          <Button title="Log Out" variant="danger" icon="log-out-outline" onPress={logout} style={{ marginTop: 18 }} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  cover: { height: 110, backgroundColor: colors.primary },
  gear: { position: 'absolute', right: 18, top: 14, width: 38, height: 38, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.2)', alignItems: 'center', justifyContent: 'center' },
  profileTop: { alignItems: 'center', marginTop: -46, paddingHorizontal: 20 },
  name: { fontSize: 22, fontWeight: '900', color: colors.ink, marginTop: 10 },
  nickname: { fontSize: 16, fontWeight: '700', color: colors.muted },
  infoRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
  infoLabel: { color: colors.muted, fontSize: 12 },
  infoValue: { color: colors.ink, fontWeight: '700', fontSize: 14.5, marginTop: 1 },
  hiddenPill: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bg, borderRadius: 999, paddingVertical: 4, paddingHorizontal: 9 },
  hiddenText: { color: colors.muted, fontSize: 11, fontWeight: '700', marginLeft: 4 },
  headline: { color: colors.body, marginTop: 3, fontWeight: '600' },
  loc: { color: colors.muted, marginTop: 4, fontSize: 13 },
  statsRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingVertical: 14, marginTop: 16, alignSelf: 'stretch' },
  stat: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 20, fontWeight: '900', color: colors.ink },
  statLabel: { color: colors.muted, fontSize: 12, marginTop: 2 },
  divider: { width: 1, height: 30, backgroundColor: colors.border },
  body: { padding: 20 },
  verifyCard: { marginBottom: 14 },
  cardTitle: { fontWeight: '800', color: colors.ink, fontSize: 15.5 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
  premiumCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.gold, borderRadius: radius.md, padding: 18, marginBottom: 6 },
  premiumTitle: { color: '#fff', fontWeight: '900', fontSize: 16 },
  premiumSub: { color: 'rgba(255,255,255,0.92)', marginTop: 3, fontSize: 13 },
  viewerRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
  blur: { letterSpacing: 2 },
  eduIcon: { width: 42, height: 42, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  menuRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, padding: 16, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, marginBottom: 8 },
  menuText: { flex: 1, marginLeft: 12, fontWeight: '700', color: colors.ink },
});
