import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, Avatar, Select, Toggle, Card, Tag, SectionTitle, ChipSelect, DateField } from '../src/components/ui';
import EducationForm from '../src/components/EducationForm';
import { colors } from '../src/theme';
import {
  GENDERS, WORK_STATUS, INDUSTRIES, INTERESTS, LANGUAGES,
  PROFILE_VISIBILITY, REQUEST_FROM, eduSummary, eduLocation,
} from '../src/data';
import { useApp } from '../src/store';

export default function EditProfile() {
  const router = useRouter();
  const { state, updateProfile, addEducation, removeEducation, logout } = useApp();
  const me = state.me || {};

  // --- Category 1: Basic Information ---
  const [name, setName] = useState(me.name || '');
  const [nickname, setNickname] = useState(me.nickname || '');
  const [gender, setGender] = useState(me.gender || '');
  const [dob, setDob] = useState(me.dob || '');
  const [photo, setPhoto] = useState(me.photo || '');

  // --- Category 3: Professional Details ---
  const p0 = me.profession || {};
  const [workStatus, setWorkStatus] = useState(p0.status || '');
  const [title, setTitle] = useState(p0.title || me.work?.title || '');
  const [company, setCompany] = useState(p0.company || me.work?.company || '');
  const [industry, setIndustry] = useState(p0.industry || '');
  const [experience, setExperience] = useState(p0.experience || '');
  const [skills, setSkills] = useState(me.skills || []);

  // --- Category 4: Contact Information ---
  const c0 = me.contact || {};
  const [mobile, setMobile] = useState(c0.mobile ?? me.mobile ?? '');
  const [email, setEmail] = useState(c0.email ?? me.email ?? '');
  const [altPhone, setAltPhone] = useState(c0.altPhone || '');
  const [address, setAddress] = useState(c0.address || '');
  const [city, setCity] = useState(c0.city ?? me.city ?? '');
  const [stateName, setStateName] = useState(c0.state ?? me.state ?? '');
  const [country, setCountry] = useState(c0.country || 'India');
  const [pincode, setPincode] = useState(c0.pincode || '');

  // --- Category 5: Social Links ---
  const s0 = me.social || {};
  const [linkedin, setLinkedin] = useState(s0.linkedin || '');
  const [instagram, setInstagram] = useState(s0.instagram || '');
  const [facebook, setFacebook] = useState(s0.facebook || '');
  const [twitter, setTwitter] = useState(s0.twitter || '');
  const [website, setWebsite] = useState(s0.website || '');
  const [github, setGithub] = useState(s0.github || '');

  // --- Category 6: Privacy Settings ---
  const pr0 = me.privacy || {};
  const [mobileHidden, setMobileHidden] = useState(pr0.mobileHidden ?? me.mobileHidden ?? true);
  const [emailHidden, setEmailHidden] = useState(pr0.emailHidden ?? me.emailHidden ?? true);
  const [profileVisibility, setProfileVisibility] = useState(pr0.profileVisibility || 'Public');
  const [requestsFrom, setRequestsFrom] = useState(pr0.requestsFrom || 'Everyone');
  const [showOnline, setShowOnline] = useState(pr0.showOnline ?? true);
  const [searchMatching, setSearchMatching] = useState(pr0.searchMatching ?? true);

  // --- Category 7: Interests ---
  const [interests, setInterests] = useState(me.interests || []);

  // --- Category 8: Account Settings ---
  const a0 = me.account || {};
  const [language, setLanguage] = useState(a0.language || 'English');
  const [pushNotif, setPushNotif] = useState(a0.pushNotif ?? true);
  const [emailNotif, setEmailNotif] = useState(a0.emailNotif ?? false);

  const save = () => {
    updateProfile({
      name: name.trim() || me.name,
      nickname: nickname.trim(),
      gender,
      dob: (dob || '').trim(),
      photo: photo.trim(),
      profession: { status: workStatus, title: title.trim(), company: company.trim(), industry, experience: experience.trim() },
      skills,
      contact: {
        mobile: mobile.trim(), email: email.trim(), altPhone: altPhone.trim(),
        address: address.trim(), city: city.trim(), state: stateName.trim(),
        country: country.trim(), pincode: pincode.trim(),
      },
      // Mirror to top-level for matchScore / header / back-compat.
      mobile: mobile.trim(), email: email.trim(), city: city.trim(), state: stateName.trim(),
      mobileHidden, emailHidden,
      social: { linkedin: linkedin.trim(), instagram: instagram.trim(), facebook: facebook.trim(), twitter: twitter.trim(), website: website.trim(), github: github.trim() },
      privacy: { mobileHidden, emailHidden, profileVisibility, requestsFrom, showOnline, searchMatching },
      interests,
      account: { language, pushNotif, emailNotif },
    });
    router.back();
  };

  const mock = (msg) => Alert.alert('Demo', msg);
  const confirmDelete = () =>
    Alert.alert('Delete Account', 'This is a demo — in production this would permanently delete your account.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: logout },
    ]);

  const education = me.education || [];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8}><Ionicons name="chevron-back" size={26} color={colors.ink} /></Pressable>
        <Text style={styles.headerTitle}>Edit Profile</Text>
        <Pressable onPress={save} hitSlop={8}><Text style={styles.save}>Save</Text></Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        {/* 1 — Basic Information */}
        <SectionTitle>Basic Information</SectionTitle>
        <View style={styles.photoRow}>
          <Avatar name={name || '?'} size={84} photo={photo || undefined} />
          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.photoHint}>Paste an image URL to set your profile photo.</Text>
            {!!photo && (
              <Pressable style={styles.photoBtn} onPress={() => setPhoto('')}>
                <Ionicons name="trash-outline" size={16} color={colors.danger} />
                <Text style={[styles.photoText, { color: colors.danger }]}>Remove Photo</Text>
              </Pressable>
            )}
          </View>
        </View>
        <Field label="Profile Photo URL" icon="image-outline" autoCapitalize="none" placeholder="https://…/photo.jpg" value={photo} onChangeText={setPhoto} />
        <Field label="Full Name *" icon="person-outline" value={name} onChangeText={setName} />
        <Field label="Nickname (optional)" icon="happy-outline" value={nickname} onChangeText={setNickname} />
        <Select label="Gender" icon="male-female-outline" placeholder="Select gender" value={gender} options={GENDERS} onChange={setGender} />
        <DateField label="Date of Birth" value={dob} onChange={setDob} />

        {/* 2 — Education Details */}
        <SectionTitle>Education Details</SectionTitle>
        {education.map((e, i) => (
          <Card key={i} style={{ marginBottom: 10, flexDirection: 'row', alignItems: 'flex-start' }}>
            <Ionicons name="school" size={20} color={colors.primary} style={{ marginRight: 12, marginTop: 2 }} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontWeight: '800', color: colors.ink }}>{e.name || e.course || e.type}</Text>
              {!!eduSummary(e) && <Text style={styles.meta}>{eduSummary(e)}</Text>}
              {!!eduLocation(e) && <Text style={styles.meta}>{eduLocation(e)}</Text>}
              <Tag label={e.type || e.level} />
            </View>
            <Pressable onPress={() => removeEducation(i)} hitSlop={8} style={{ padding: 4 }}>
              <Ionicons name="trash-outline" size={20} color={colors.danger} />
            </Pressable>
          </Card>
        ))}
        {education.length === 0 && <Text style={styles.meta}>No education added yet.</Text>}
        <Text style={styles.subLabel}>Add a record</Text>
        <EducationForm onAdd={addEducation} />

        {/* 3 — Professional Details */}
        <SectionTitle>Professional Details</SectionTitle>
        <Select label="Current Status" icon="briefcase-outline" placeholder="Select status" value={workStatus} options={WORK_STATUS} onChange={setWorkStatus} />
        <Field label="Job Title / Designation" icon="id-card-outline" value={title} onChangeText={setTitle} placeholder="e.g. Software Engineer" />
        <Field label="Company / Organization" icon="business-outline" value={company} onChangeText={setCompany} />
        <Select label="Industry" icon="layers-outline" placeholder="Select industry" value={industry} options={INDUSTRIES} onChange={setIndustry} />
        <Field label="Experience" icon="time-outline" value={experience} onChangeText={setExperience} placeholder="e.g. 3 years" />
        <ChipSelect label="Skills" options={[]} values={skills} onChange={setSkills} allowCustom placeholder="Add a skill" />

        {/* 4 — Contact Information */}
        <SectionTitle>Contact Information</SectionTitle>
        <Field label="Mobile Number" icon="call-outline" keyboardType="phone-pad" value={mobile} onChangeText={setMobile} />
        <Field label="Email ID" icon="mail-outline" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail} />
        <Field label="Alternate Phone" icon="call-outline" keyboardType="phone-pad" value={altPhone} onChangeText={setAltPhone} />
        <Field label="Address" icon="home-outline" value={address} onChangeText={setAddress} />
        <Field label="City" icon="location-outline" value={city} onChangeText={setCity} />
        <Field label="State" icon="map-outline" value={stateName} onChangeText={setStateName} />
        <Field label="Country" icon="earth-outline" value={country} onChangeText={setCountry} />
        <Field label="Pincode" icon="pin-outline" keyboardType="number-pad" value={pincode} onChangeText={setPincode} />

        {/* 5 — Social Links */}
        <SectionTitle>Social Links (Optional)</SectionTitle>
        <Field label="LinkedIn" icon="logo-linkedin" autoCapitalize="none" value={linkedin} onChangeText={setLinkedin} placeholder="linkedin.com/in/…" />
        <Field label="Instagram" icon="logo-instagram" autoCapitalize="none" value={instagram} onChangeText={setInstagram} placeholder="@username" />
        <Field label="Facebook" icon="logo-facebook" autoCapitalize="none" value={facebook} onChangeText={setFacebook} />
        <Field label="Twitter / X" icon="logo-twitter" autoCapitalize="none" value={twitter} onChangeText={setTwitter} placeholder="@username" />
        <Field label="Website" icon="globe-outline" autoCapitalize="none" value={website} onChangeText={setWebsite} placeholder="https://…" />
        <Field label="GitHub" icon="logo-github" autoCapitalize="none" value={github} onChangeText={setGithub} placeholder="@username" />

        {/* 6 — Privacy Settings */}
        <SectionTitle>Privacy Settings</SectionTitle>
        <Toggle label="Hide mobile number" icon="eye-off-outline" value={mobileHidden} onValueChange={setMobileHidden} />
        <Toggle label="Hide email ID" icon="eye-off-outline" value={emailHidden} onValueChange={setEmailHidden} />
        <Select label="Profile Visibility" icon="shield-outline" value={profileVisibility} options={PROFILE_VISIBILITY} onChange={setProfileVisibility} />
        <Select label="Who can send requests" icon="person-add-outline" value={requestsFrom} options={REQUEST_FROM} onChange={setRequestsFrom} />
        <Toggle label="Show online status" icon="ellipse-outline" value={showOnline} onValueChange={setShowOnline} />
        <Toggle label="Appear in search matching" icon="search-outline" value={searchMatching} onValueChange={setSearchMatching} />

        {/* 7 — Interests */}
        <SectionTitle>Interests (Optional)</SectionTitle>
        <ChipSelect options={INTERESTS} values={interests} onChange={setInterests} allowCustom placeholder="Add your own interest" />

        {/* 8 — Account Settings */}
        <SectionTitle>Account Settings</SectionTitle>
        <Select label="Preferred Language" icon="language-outline" value={language} options={LANGUAGES} onChange={setLanguage} />
        <Toggle label="Push notifications" icon="notifications-outline" value={pushNotif} onValueChange={setPushNotif} />
        <Toggle label="Email notifications" icon="mail-unread-outline" value={emailNotif} onValueChange={setEmailNotif} />
        <Button title="Change Password" variant="ghost" icon="key-outline" onPress={() => mock('Password change is stubbed in this build.')} style={{ marginBottom: 10 }} />
        <Button title="Deactivate Account" variant="ghost" icon="pause-circle-outline" onPress={() => mock('Account deactivation is stubbed in this build.')} style={{ marginBottom: 10 }} />
        <Button title="Delete Account" variant="danger" icon="trash-outline" onPress={confirmDelete} style={{ marginBottom: 10 }} />
        <Button title="Log Out" variant="danger" icon="log-out-outline" onPress={logout} />

        {/* 9 — Premium Features */}
        <SectionTitle>Premium Features</SectionTitle>
        <Pressable onPress={() => router.push('/premium')} style={styles.premiumCard}>
          <View style={{ flex: 1 }}>
            <Text style={styles.premiumTitle}>{state.premium ? '⭐ Premium Active' : 'Upgrade to Premium'}</Text>
            <Text style={styles.premiumSub}>{state.premium ? 'You have unlimited access.' : 'See who viewed you, unlimited chats & filters.'}</Text>
          </View>
          <Ionicons name="chevron-forward" size={22} color="#fff" />
        </Pressable>

        <Button title="Save Changes" icon="checkmark-circle" onPress={save} style={{ marginTop: 18 }} />
        <View style={{ height: 30 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 18, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  headerTitle: { fontWeight: '900', fontSize: 17, color: colors.ink },
  save: { color: colors.primary, fontWeight: '800', fontSize: 15.5 },
  wrap: { padding: 20 },
  photoRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  photoBtn: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', marginTop: 8, backgroundColor: colors.primarySoft, paddingVertical: 8, paddingHorizontal: 14, borderRadius: 12 },
  photoText: { color: colors.primary, fontWeight: '800', marginLeft: 7 },
  photoHint: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
  subLabel: { fontWeight: '800', color: colors.ink, fontSize: 14.5, marginTop: 10, marginBottom: 12 },
  premiumCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.gold, borderRadius: 16, padding: 18 },
  premiumTitle: { color: '#fff', fontWeight: '900', fontSize: 16 },
  premiumSub: { color: 'rgba(255,255,255,0.92)', marginTop: 3, fontSize: 13 },
});
