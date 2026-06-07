import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Tag, Button, SectionTitle } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp } from '../../src/store';
import { getUser, eduSummary, eduLocation } from '../../src/data';

// One labelled row inside a category card.
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

// Read-only tag cloud for skills / interests.
function TagCloud({ items }) {
  if (!items || !items.length) return null;
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
      {items.map((t) => <Tag key={t} label={t} />)}
    </View>
  );
}

export default function Profile() {
  const router = useRouter();
  const { state, friendsList, logout } = useApp();
  const me = state.me || {};
  const edit = () => router.push('/edit-profile');

  const prof = me.profession || {};
  const contact = me.contact || {};
  const social = me.social || {};
  const privacy = me.privacy || {};
  const account = me.account || {};

  const mobile = contact.mobile ?? me.mobile;
  const email = contact.email ?? me.email;
  const mobileHidden = privacy.mobileHidden ?? me.mobileHidden;
  const emailHidden = privacy.emailHidden ?? me.emailHidden;

  const socialLinks = [
    ['logo-linkedin', 'LinkedIn', social.linkedin],
    ['logo-instagram', 'Instagram', social.instagram],
    ['logo-facebook', 'Facebook', social.facebook],
    ['logo-twitter', 'Twitter / X', social.twitter],
    ['globe-outline', 'Website', social.website],
    ['logo-github', 'GitHub', social.github],
  ].filter(([, , v]) => !!v);

  const hasBasic = me.nickname || me.gender || me.dob;
  const hasProf = prof.status || prof.title || prof.company || prof.industry || prof.experience || (me.skills || []).length;
  const hasContact = mobile || email || contact.altPhone || contact.address || me.city || me.state || contact.country || contact.pincode;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScrollView contentContainerStyle={{ paddingBottom: 28 }} showsVerticalScrollIndicator={false}>
        {/* Header */}
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
          {/* 1 — Basic Information */}
          <SectionTitle action="Edit" onAction={edit}>Basic Information</SectionTitle>
          <Card>
            <InfoRow icon="happy-outline" label="Nickname" value={me.nickname} />
            <InfoRow icon="male-female-outline" label="Gender" value={me.gender} />
            <InfoRow icon="calendar-outline" label="Date of Birth" value={me.dob} />
            {!hasBasic && <Text style={styles.meta}>Tap Edit to add your details.</Text>}
          </Card>

          {/* 2 — Education Details */}
          <SectionTitle action="Add / Edit" onAction={edit}>Education Details</SectionTitle>
          {(me.education || []).map((e, i) => (
            <Card key={i} style={{ marginBottom: 10, flexDirection: 'row', alignItems: 'flex-start' }}>
              <View style={styles.eduIcon}><Ionicons name="school" size={20} color={colors.primary} /></View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{e.name || e.course || e.type}</Text>
                {!!eduSummary(e) && <Text style={styles.meta}>{eduSummary(e)}</Text>}
                {!!eduLocation(e) && <Text style={styles.meta}>{eduLocation(e)}</Text>}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' }}>
                  <Tag label={e.type || e.level} />
                  {!!e.status && <Tag label={e.status} color={e.status === 'Completed' ? colors.success : e.status === 'Discontinued' ? colors.danger : colors.accent} />}
                </View>
                {!!e.visibility && (
                  <Text style={styles.metaSmall}>
                    <Ionicons name="eye-outline" size={11} color={colors.muted} /> {e.visibility}
                    {e.searchMatching ? ' · Search matching on' : ''}
                  </Text>
                )}
              </View>
            </Card>
          ))}
          {(!me.education || me.education.length === 0) && (
            <Card><Text style={styles.meta}>No education added yet.</Text></Card>
          )}

          {/* 3 — Professional Details */}
          <SectionTitle action="Edit" onAction={edit}>Professional Details</SectionTitle>
          <Card>
            <InfoRow icon="briefcase-outline" label="Current Status" value={prof.status} />
            <InfoRow icon="id-card-outline" label="Designation" value={[prof.title, prof.company].filter(Boolean).join(' @ ')} />
            <InfoRow icon="layers-outline" label="Industry" value={prof.industry} />
            <InfoRow icon="time-outline" label="Experience" value={prof.experience} />
            {(me.skills || []).length > 0 && (
              <View style={{ marginTop: 10 }}>
                <Text style={styles.infoLabel}>Skills</Text>
                <View style={{ marginTop: 4 }}><TagCloud items={me.skills} /></View>
              </View>
            )}
            {!hasProf && <Text style={styles.meta}>Tap Edit to add your professional details.</Text>}
          </Card>

          {/* 4 — Contact Information */}
          <SectionTitle action="Edit" onAction={edit}>Contact Information</SectionTitle>
          <Card>
            <InfoRow icon="call-outline" label="Mobile Number" value={mobile} hidden={mobileHidden} />
            <InfoRow icon="mail-outline" label="Email ID" value={email} hidden={emailHidden} />
            <InfoRow icon="call-outline" label="Alternate Phone" value={contact.altPhone} />
            <InfoRow icon="home-outline" label="Address" value={contact.address} />
            <InfoRow icon="location-outline" label="City / State" value={[me.city, me.state].filter(Boolean).join(', ')} />
            <InfoRow icon="earth-outline" label="Country" value={contact.country} />
            <InfoRow icon="pin-outline" label="Pincode" value={contact.pincode} />
            {!hasContact && <Text style={styles.meta}>Tap Edit to add your contact information.</Text>}
          </Card>

          {/* 5 — Social Links */}
          {socialLinks.length > 0 && (
            <>
              <SectionTitle action="Edit" onAction={edit}>Social Links</SectionTitle>
              <Card>
                {socialLinks.map(([icon, label, value], i) => (
                  <View key={label} style={[styles.infoRow, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
                    <Ionicons name={icon} size={18} color={colors.primary} style={{ marginRight: 12 }} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.infoLabel}>{label}</Text>
                      <Text style={styles.infoValue} numberOfLines={1}>{value}</Text>
                    </View>
                  </View>
                ))}
              </Card>
            </>
          )}

          {/* 6 — Interests */}
          {(me.interests || []).length > 0 && (
            <>
              <SectionTitle action="Edit" onAction={edit}>Interests</SectionTitle>
              <Card><TagCloud items={me.interests} /></Card>
            </>
          )}

          {/* 7 — Privacy Settings */}
          <SectionTitle action="Edit" onAction={edit}>Privacy Settings</SectionTitle>
          <Card>
            <InfoRow icon="shield-outline" label="Profile Visibility" value={privacy.profileVisibility || 'Public'} />
            <InfoRow icon="person-add-outline" label="Who can send requests" value={privacy.requestsFrom || 'Everyone'} />
            <InfoRow icon="ellipse-outline" label="Show online status" value={(privacy.showOnline ?? true) ? 'On' : 'Off'} />
            <InfoRow icon="search-outline" label="Search matching" value={(privacy.searchMatching ?? true) ? 'On' : 'Off'} />
            <InfoRow icon="eye-off-outline" label="Mobile hidden" value={mobileHidden ? 'Yes' : 'No'} />
            <InfoRow icon="eye-off-outline" label="Email hidden" value={emailHidden ? 'Yes' : 'No'} />
          </Card>

          {/* 8 — Account Settings */}
          <SectionTitle action="Edit" onAction={edit}>Account Settings</SectionTitle>
          <Card>
            <InfoRow icon="language-outline" label="Preferred Language" value={account.language || 'English'} />
            <InfoRow icon="notifications-outline" label="Push notifications" value={(account.pushNotif ?? true) ? 'On' : 'Off'} />
            <InfoRow icon="mail-unread-outline" label="Email notifications" value={(account.emailNotif ?? false) ? 'On' : 'Off'} />
          </Card>
          <Card style={styles.verifyCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Ionicons name={me.verified ? 'shield-checkmark' : 'shield-outline'} size={26} color={me.verified ? colors.success : colors.warning} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{me.verified ? 'Verified Profile' : 'Get Verified'}</Text>
                <Text style={styles.meta}>{me.verified ? 'Your batch & ID are confirmed.' : 'Verify college email or student ID to build trust.'}</Text>
              </View>
            </View>
            {!me.verified && <Button small title="Verify Now" variant="soft" icon="mail" style={{ marginTop: 12, alignSelf: 'flex-start' }} />}
          </Card>
          <Button title="Log Out" variant="danger" icon="log-out-outline" onPress={logout} style={{ marginTop: 4, marginBottom: 8 }} />

          {/* 9 — Premium Features */}
          <SectionTitle>Premium Features</SectionTitle>
          <Pressable onPress={() => router.push('/premium')} style={styles.premiumCard}>
            <View style={{ flex: 1 }}>
              <Text style={styles.premiumTitle}>{state.premium ? '⭐ Premium Active' : 'Upgrade to Premium'}</Text>
              <Text style={styles.premiumSub}>{state.premium ? 'You have unlimited access.' : 'See who viewed you, unlimited chats & filters.'}</Text>
            </View>
            <Ionicons name="chevron-forward" size={22} color="#fff" />
          </Pressable>
          <Text style={styles.subTitle}>Who Viewed Your Profile</Text>
          <Card>
            {state.profileViewers.slice(0, 3).map((id, i) => {
              const u = getUser(id);
              const locked = !state.premium;
              return (
                <View key={id} style={[styles.viewerRow, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
                  <Avatar name={locked ? '? ?' : u?.name} size={42} />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={[styles.cardTitle, { fontSize: 15 }, locked && styles.blur]}>{locked ? '••••••••' : u?.name}</Text>
                    <Text style={styles.meta}>{locked ? 'Upgrade to reveal' : u?.headline}</Text>
                  </View>
                  {locked ? <Ionicons name="lock-closed" size={18} color={colors.gold} /> : <Ionicons name="chevron-forward" size={18} color={colors.muted} />}
                </View>
              );
            })}
          </Card>
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
  headline: { color: colors.body, marginTop: 3, fontWeight: '600' },
  loc: { color: colors.muted, marginTop: 4, fontSize: 13 },
  statsRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingVertical: 14, marginTop: 16, alignSelf: 'stretch' },
  stat: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 20, fontWeight: '900', color: colors.ink },
  statLabel: { color: colors.muted, fontSize: 12, marginTop: 2 },
  divider: { width: 1, height: 30, backgroundColor: colors.border },
  body: { padding: 20 },
  cardTitle: { fontWeight: '800', color: colors.ink, fontSize: 15.5 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
  metaSmall: { color: colors.muted, fontSize: 12, marginTop: 6 },
  infoRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
  infoLabel: { color: colors.muted, fontSize: 12 },
  infoValue: { color: colors.ink, fontWeight: '700', fontSize: 14.5, marginTop: 1 },
  hiddenPill: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bg, borderRadius: 999, paddingVertical: 4, paddingHorizontal: 9 },
  hiddenText: { color: colors.muted, fontSize: 11, fontWeight: '700', marginLeft: 4 },
  eduIcon: { width: 42, height: 42, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  verifyCard: { marginTop: 10 },
  premiumCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.gold, borderRadius: radius.md, padding: 18 },
  premiumTitle: { color: '#fff', fontWeight: '900', fontSize: 16 },
  premiumSub: { color: 'rgba(255,255,255,0.92)', marginTop: 3, fontSize: 13 },
  subTitle: { fontSize: 16, fontWeight: '800', color: colors.ink, marginTop: 16, marginBottom: 10 },
  viewerRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
  blur: { letterSpacing: 2 },
});
