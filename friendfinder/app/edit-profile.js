import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Alert } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, Avatar, Select, Toggle, SectionTitle, ChipSelect, DateField } from '../src/components/ui';
import EducationForm from '../src/components/EducationForm';
import EducationCard from '../src/components/EducationCard';
import { colors, radius } from '../src/theme';
import {
  GENDERS, WORK_STATUS, INDUSTRIES, INTERESTS, HOBBIES, LOOKING_FOR, LANGUAGES,
  PROFILE_VISIBILITY, REQUEST_FROM, PREMIUM_FEATURES,
} from '../src/data';
import { useApp } from '../src/store';

const SECTION_TITLES = {
  basic: 'Basic Information', education: 'Education Details', professional: 'Professional Details',
  contact: 'Contact Information', social: 'Social Links', privacy: 'Privacy Settings',
  interests: 'Interests', account: 'Account Settings', premium: 'Premium Features',
  timeline: 'Personal Timeline', matching: 'Friend Matching', memory: 'Education Memory',
  unique: 'Memory Wall & Unique Features',
};

export default function EditProfile() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const section = params.section || 'all';
  const show = (k) => section === 'all' || section === k;
  const { state, updateProfile, addEducation, updateEducation, removeEducation, friendsList, logout, deactivate } = useApp();
  const me = state.me || {};

  // Education Details — which record is being edited, and whether we're adding one.
  const [editingEdu, setEditingEdu] = useState(null); // index of record being edited
  const [addingEdu, setAddingEdu] = useState(false);

  // 1 — Basic Information
  const [name, setName] = useState(me.name || '');
  const [nickname, setNickname] = useState(me.nickname || '');
  const [gender, setGender] = useState(me.gender || '');
  const [dob, setDob] = useState(me.dob || '');
  const [photo, setPhoto] = useState(me.photo || '');

  // 3 — Professional Details
  const p0 = me.profession || {};
  const [workStatus, setWorkStatus] = useState(p0.status || '');
  const [title, setTitle] = useState(p0.title || me.work?.title || '');
  const [company, setCompany] = useState(p0.company || me.work?.company || '');
  const [industry, setIndustry] = useState(p0.industry || '');
  const [experience, setExperience] = useState(p0.experience || '');
  const [skills, setSkills] = useState(me.skills || []);

  // 4 — Contact Information
  const c0 = me.contact || {};
  const [mobile, setMobile] = useState(c0.mobile ?? me.mobile ?? '');
  const [email, setEmail] = useState(c0.email ?? me.email ?? '');
  const [altPhone, setAltPhone] = useState(c0.altPhone || '');
  const [address, setAddress] = useState(c0.address || '');
  const [city, setCity] = useState(c0.city ?? me.city ?? '');
  const [stateName, setStateName] = useState(c0.state ?? me.state ?? '');
  const [country, setCountry] = useState(c0.country || 'India');
  const [pincode, setPincode] = useState(c0.pincode || '');
  const mobileVerified = !!c0.mobileVerified && c0.mobile === mobile.trim();
  const emailVerified = !!c0.emailVerified && c0.email === email.trim();

  // 5 — Social Links
  const s0 = me.social || {};
  const [linkedin, setLinkedin] = useState(s0.linkedin || '');
  const [instagram, setInstagram] = useState(s0.instagram || '');
  const [facebook, setFacebook] = useState(s0.facebook || '');
  const [twitter, setTwitter] = useState(s0.twitter || '');
  const [website, setWebsite] = useState(s0.website || '');
  const [github, setGithub] = useState(s0.github || '');

  // 6 — Privacy Settings
  const pr0 = me.privacy || {};
  const [mobileHidden, setMobileHidden] = useState(pr0.mobileHidden ?? me.mobileHidden ?? true);
  const [emailHidden, setEmailHidden] = useState(pr0.emailHidden ?? me.emailHidden ?? true);
  const [profileVisibility, setProfileVisibility] = useState(pr0.profileVisibility || 'Public');
  const [requestsFrom, setRequestsFrom] = useState(pr0.requestsFrom || 'Everyone');
  const [showOnline, setShowOnline] = useState(pr0.showOnline ?? true);
  const [searchMatching, setSearchMatching] = useState(pr0.searchMatching ?? true);

  // 7 — Interests
  const [interests, setInterests] = useState(me.interests || []);

  // 7b — Interests & Hobbies
  const [hobbies, setHobbies] = useState(me.hobbies || []);
  const [customTags, setCustomTags] = useState(me.customTags || []);

  // 8 — Account Settings
  const a0 = me.account || {};
  const [language, setLanguage] = useState(a0.language || 'English');
  const [pushNotif, setPushNotif] = useState(a0.pushNotif ?? true);
  const [emailNotif, setEmailNotif] = useState(a0.emailNotif ?? false);
  const [twoFactor, setTwoFactor] = useState(a0.twoFactor ?? false);

  // 9 — Personal Timeline
  const [timeline, setTimeline] = useState(me.timeline || {});
  const setT = (k, v) => setTimeline((o) => ({ ...o, [k]: v }));

  // 10 — Friend Matching
  const [lookingFor, setLookingFor] = useState(me.lookingFor || []);
  const [matching, setMatching] = useState(me.matching || {});
  const setM = (k, v) => setMatching((o) => ({ ...o, [k]: v }));

  // 11 — Education Memory
  const [eduMemory, setEduMemory] = useState(me.eduMemory || {});
  const setEM = (k, v) => setEduMemory((o) => ({ ...o, [k]: v }));

  // 12 — Memory Wall & Unique Features
  const [unique, setUnique] = useState(me.unique || {});
  const setU = (k, v) => setUnique((o) => ({ ...o, [k]: v }));

  const save = () => {
    const base = me.contact || {};
    const newMobile = mobile.trim();
    const newEmail = email.trim();
    updateProfile({
      name: name.trim() || me.name,
      nickname: nickname.trim(),
      gender,
      dob: (dob || '').trim(),
      photo: photo.trim(),
      profession: { status: workStatus, title: title.trim(), company: company.trim(), industry, experience: experience.trim() },
      skills,
      contact: {
        ...base,
        mobile: newMobile, email: newEmail, altPhone: altPhone.trim(),
        address: address.trim(), city: city.trim(), state: stateName.trim(),
        country: country.trim(), pincode: pincode.trim(),
        // Editing the value resets its verified flag.
        mobileVerified: newMobile === base.mobile ? !!base.mobileVerified : false,
        emailVerified: newEmail === base.email ? !!base.emailVerified : false,
      },
      mobile: newMobile, email: newEmail, city: city.trim(), state: stateName.trim(),
      mobileHidden, emailHidden,
      social: { linkedin: linkedin.trim(), instagram: instagram.trim(), facebook: facebook.trim(), twitter: twitter.trim(), website: website.trim(), github: github.trim() },
      privacy: { mobileHidden, emailHidden, profileVisibility, requestsFrom, showOnline, searchMatching },
      interests,
      hobbies,
      customTags,
      account: { language, pushNotif, emailNotif, twoFactor },
      timeline,
      lookingFor,
      matching,
      eduMemory,
      unique,
    });
    router.back();
  };

  const mock = (title, msg) => Alert.alert(title, msg);
  const confirmDeactivate = () =>
    Alert.alert(
      'Deactivate Account',
      'Your account will be temporarily deactivated. You can reactivate it anytime by logging in again.',
      [{ text: 'Cancel', style: 'cancel' }, { text: 'Deactivate', style: 'destructive', onPress: () => { deactivate(); router.replace('/deactivated'); } }]
    );
  const logoutAll = () =>
    Alert.alert('Log out from all devices', 'You will be signed out everywhere. Continue?', [
      { text: 'Cancel', style: 'cancel' }, { text: 'Log Out All', style: 'destructive', onPress: logout },
    ]);

  const verify = (type) =>
    router.push({ pathname: '/account/verify', params: { type, value: type === 'mobile' ? mobile : email } });

  const education = me.education || [];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8}><Ionicons name="chevron-back" size={26} color={colors.ink} /></Pressable>
        <Text style={styles.headerTitle}>{section === 'all' ? 'Edit Profile' : SECTION_TITLES[section] || 'Edit Profile'}</Text>
        <Pressable onPress={save} hitSlop={8}><Text style={styles.save}>Save</Text></Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        {show('basic') && (<>
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
        </>)}

        {show('education') && (<>
          <SectionTitle>Education Details</SectionTitle>
          {education.map((e, i) => (
            editingEdu === i ? (
              <EducationForm
                key={i}
                mode="edit"
                initial={e}
                saveLabel="Save Changes"
                onSave={(entry) => { updateEducation(i, entry); setEditingEdu(null); }}
                onCancel={() => setEditingEdu(null)}
              />
            ) : (
              <EducationCard
                key={i}
                entry={e}
                onEdit={() => { setEditingEdu(i); setAddingEdu(false); }}
                onRemove={() => removeEducation(i)}
              />
            )
          ))}
          {education.length === 0 && <Text style={styles.meta}>No education added yet.</Text>}

          {addingEdu ? (
            <View style={{ marginTop: 12 }}>
              <Text style={styles.subLabel}>Add institution</Text>
              <EducationForm
                mode="edit"
                initial={{}}
                saveLabel="Add this institution"
                onSave={(entry) => { addEducation(entry); setAddingEdu(false); }}
                onCancel={() => setAddingEdu(false)}
              />
            </View>
          ) : (
            editingEdu === null && (
              <Button
                title="Add more institution"
                variant="soft"
                icon="add-circle-outline"
                onPress={() => setAddingEdu(true)}
                style={{ marginTop: 12 }}
              />
            )
          )}
        </>)}

        {show('professional') && (<>
          <SectionTitle>Professional Details</SectionTitle>
          <SelectOrManual label="Current Status" icon="briefcase-outline" placeholder="Select status" value={workStatus} options={WORK_STATUS} onChange={setWorkStatus} />
          <Field label="Job Title / Designation" icon="id-card-outline" value={title} onChangeText={setTitle} placeholder="e.g. Software Engineer" />
          <Field label="Company / Organization" icon="business-outline" value={company} onChangeText={setCompany} />
          <SelectOrManual label="Industry" icon="layers-outline" placeholder="Select industry" value={industry} options={INDUSTRIES} onChange={setIndustry} />
          <Field label="Experience" icon="time-outline" value={experience} onChangeText={setExperience} placeholder="e.g. 3 years" />
          <ChipSelect label="Skills" options={[]} values={skills} onChange={setSkills} allowCustom placeholder="Add a skill" />
        </>)}

        {show('contact') && (<>
          <SectionTitle>Contact Information</SectionTitle>
          <Field label="Mobile Number" icon="call-outline" keyboardType="phone-pad" value={mobile} onChangeText={setMobile} />
          <VerifyRow verified={mobileVerified} canVerify={!!mobile.trim()} onVerify={() => verify('mobile')} label="mobile number" />
          <Field label="Email ID" icon="mail-outline" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail} />
          <VerifyRow verified={emailVerified} canVerify={!!email.trim()} onVerify={() => verify('email')} label="email address" />
          <ActionRow icon="swap-horizontal-outline" label="Change & Verify Mobile Number" onPress={() => verify('mobile')} />
          <ActionRow icon="swap-horizontal-outline" label="Change & Verify Email Address" onPress={() => verify('email')} />
          <Field label="Alternate Phone" icon="call-outline" keyboardType="phone-pad" value={altPhone} onChangeText={setAltPhone} />
          <Field label="Address" icon="home-outline" value={address} onChangeText={setAddress} />
          <Field label="City" icon="location-outline" value={city} onChangeText={setCity} />
          <Field label="State" icon="map-outline" value={stateName} onChangeText={setStateName} />
          <Field label="Country" icon="earth-outline" value={country} onChangeText={setCountry} />
          <Field label="Pincode" icon="pin-outline" keyboardType="number-pad" value={pincode} onChangeText={setPincode} />
        </>)}

        {show('social') && (<>
          <SectionTitle>Social Links (Optional)</SectionTitle>
          <Field label="LinkedIn" icon="logo-linkedin" autoCapitalize="none" value={linkedin} onChangeText={setLinkedin} placeholder="linkedin.com/in/…" />
          <Field label="Instagram" icon="logo-instagram" autoCapitalize="none" value={instagram} onChangeText={setInstagram} placeholder="@username" />
          <Field label="Facebook" icon="logo-facebook" autoCapitalize="none" value={facebook} onChangeText={setFacebook} />
          <Field label="Twitter / X" icon="logo-twitter" autoCapitalize="none" value={twitter} onChangeText={setTwitter} placeholder="@username" />
          <Field label="Website" icon="globe-outline" autoCapitalize="none" value={website} onChangeText={setWebsite} placeholder="https://…" />
          <Field label="GitHub" icon="logo-github" autoCapitalize="none" value={github} onChangeText={setGithub} placeholder="@username" />
        </>)}

        {show('privacy') && (<>
          <SectionTitle>Privacy Settings</SectionTitle>
          <Toggle label="Hide mobile number" icon="eye-off-outline" value={mobileHidden} onValueChange={setMobileHidden} />
          <Toggle label="Hide email ID" icon="eye-off-outline" value={emailHidden} onValueChange={setEmailHidden} />
          <Select label="Profile Visibility" icon="shield-outline" value={profileVisibility} options={PROFILE_VISIBILITY} onChange={setProfileVisibility} />
          <Select label="Who can send requests" icon="person-add-outline" value={requestsFrom} options={REQUEST_FROM} onChange={setRequestsFrom} />
          <Toggle label="Show online status" icon="ellipse-outline" value={showOnline} onValueChange={setShowOnline} />
          <Toggle label="Appear in search matching" icon="search-outline" value={searchMatching} onValueChange={setSearchMatching} />
        </>)}

        {show('interests') && (<>
          <SectionTitle>Interests</SectionTitle>
          <Text style={styles.subLabel}>Personal Interests</Text>
          <ChipSelect options={INTERESTS} values={interests} onChange={setInterests} allowCustom placeholder="Add your own interest" />
          <Text style={styles.subLabel}>Hobbies</Text>
          <ChipSelect options={HOBBIES} values={hobbies} onChange={setHobbies} allowCustom placeholder="Add a hobby" />
          <Text style={styles.subLabel}>Custom Interest Tags</Text>
          <ChipSelect options={[]} values={customTags} onChange={setCustomTags} allowCustom placeholder="Add a custom tag" />
        </>)}

        {show('account') && (<>
          <SectionTitle>Account Settings</SectionTitle>
          <Select label="Preferred Language" icon="language-outline" value={language} options={LANGUAGES} onChange={setLanguage} />
          <Toggle label="Push notifications" icon="notifications-outline" value={pushNotif} onValueChange={setPushNotif} />
          <Toggle label="Email notifications" icon="mail-unread-outline" value={emailNotif} onValueChange={setEmailNotif} />

          <Text style={styles.subLabel}>🔐 Password & Security</Text>
          <ActionRow icon="key-outline" label="Change Password" onPress={() => router.push('/account/change-password')} />
          <View style={{ marginVertical: 4 }}>
            <Toggle label="Two-Factor Authentication (2FA)" icon="shield-checkmark-outline" value={twoFactor} onValueChange={setTwoFactor} hint="Require a code at login for extra security." />
          </View>
          <ActionRow icon="pulse-outline" label="Login Activity" onPress={() => mock('Login Activity', 'Last login: Today, this device\nPrevious: Yesterday, Chrome on Windows\n(Demo data)')} />
          <ActionRow icon="phone-portrait-outline" label="Active Devices" onPress={() => mock('Active Devices', 'This device (current)\nPixel 7 — Chennai\nWindows PC — Chennai\n(Demo data)')} />
          <ActionRow icon="log-out-outline" label="Logout from All Devices" danger onPress={logoutAll} />

          <Text style={styles.subLabel}>Account</Text>
          <ActionRow icon="pause-circle-outline" label="Deactivate Account" onPress={confirmDeactivate} />
          <ActionRow icon="trash-outline" label="Delete Account" danger onPress={() => router.push('/account/delete-account')} />
          <Button title="Log Out" variant="danger" icon="log-out-outline" onPress={logout} style={{ marginTop: 8 }} />
        </>)}

        {show('timeline') && (<>
          <SectionTitle>Personal Timeline</SectionTitle>
          <Field label="School Joined Year" icon="calendar-outline" keyboardType="number-pad" value={timeline.schoolJoined || ''} onChangeText={(t) => setT('schoolJoined', t)} />
          <Field label="School Left Year" icon="calendar-outline" keyboardType="number-pad" value={timeline.schoolLeft || ''} onChangeText={(t) => setT('schoolLeft', t)} />
          <Field label="College Joined Year" icon="calendar-outline" keyboardType="number-pad" value={timeline.collegeJoined || ''} onChangeText={(t) => setT('collegeJoined', t)} />
          <Field label="College Passed Out Year" icon="calendar-outline" keyboardType="number-pad" value={timeline.collegePassed || ''} onChangeText={(t) => setT('collegePassed', t)} />
          <Field label="First Job Year" icon="briefcase-outline" keyboardType="number-pad" value={timeline.firstJob || ''} onChangeText={(t) => setT('firstJob', t)} />
          <Field label="Current City" icon="location-outline" value={timeline.currentCity || ''} onChangeText={(t) => setT('currentCity', t)} />
          <Field label="Achievements" icon="trophy-outline" multiline value={timeline.achievements || ''} onChangeText={(t) => setT('achievements', t)} placeholder="Awards, milestones, highlights…" />
        </>)}

        {show('matching') && (<>
          <SectionTitle>Friend Matching</SectionTitle>
          <Text style={styles.subLabel}>Looking For</Text>
          <ChipSelect options={LOOKING_FOR} values={lookingFor} onChange={setLookingFor} allowCustom placeholder="Add who you're looking for" />
          <Field label="Missing Friends List" icon="people-outline" multiline value={matching.missingFriends || ''} onChangeText={(t) => setM('missingFriends', t)} placeholder="Names of friends you're trying to find…" />
          <Field label="Last Seen Institution" icon="business-outline" value={matching.lastSeenInstitution || ''} onChangeText={(t) => setM('lastSeenInstitution', t)} />
          <View style={styles.infoStat}>
            <Ionicons name="checkmark-done-outline" size={18} color={colors.success} />
            <Text style={styles.infoStatText}>Number of Friends Found: {friendsList.length}</Text>
          </View>
        </>)}

        {show('memory') && (<>
          <SectionTitle>Education Memory</SectionTitle>
          <Field label="Favorite Teacher" icon="person-outline" value={eduMemory.favoriteTeacher || ''} onChangeText={(t) => setEM('favoriteTeacher', t)} />
          <Field label="Favorite Subject" icon="book-outline" value={eduMemory.favoriteSubject || ''} onChangeText={(t) => setEM('favoriteSubject', t)} />
          <Field label="Classroom / Block Name" icon="grid-outline" value={eduMemory.classroom || ''} onChangeText={(t) => setEM('classroom', t)} />
          <Field label="Hostel Name" icon="bed-outline" value={eduMemory.hostelName || ''} onChangeText={(t) => setEM('hostelName', t)} />
          <Field label="Bus Route Number" icon="bus-outline" value={eduMemory.busRoute || ''} onChangeText={(t) => setEM('busRoute', t)} />
          <Field label="Batch Photo (URL)" icon="image-outline" autoCapitalize="none" value={eduMemory.batchPhoto || ''} onChangeText={(t) => setEM('batchPhoto', t)} placeholder="https://…" />
          <Field label="Farewell Photo (URL)" icon="image-outline" autoCapitalize="none" value={eduMemory.farewellPhoto || ''} onChangeText={(t) => setEM('farewellPhoto', t)} placeholder="https://…" />
          <Field label="Convocation Photo (URL)" icon="image-outline" autoCapitalize="none" value={eduMemory.convocationPhoto || ''} onChangeText={(t) => setEM('convocationPhoto', t)} placeholder="https://…" />
        </>)}

        {show('unique') && (<>
          <SectionTitle>Memory Wall & Unique Features</SectionTitle>
          <Toggle label={'"Do You Remember Me?" Button'} icon="help-circle-outline" hint="Let batchmates ping you to jog their memory." value={!!unique.doYouRememberMe} onValueChange={(v) => setU('doYouRememberMe', v)} />
          <Field label="Batch Memories" icon="book-outline" multiline value={unique.batchMemories || ''} onChangeText={(t) => setU('batchMemories', t)} placeholder="Share a favourite memory…" />
          <Field label="Old Photos Archive (URLs)" icon="images-outline" autoCapitalize="none" multiline value={unique.oldPhotos || ''} onChangeText={(t) => setU('oldPhotos', t)} placeholder="Comma-separated image URLs" />
          <Field label="Lost Contact Since (Year)" icon="time-outline" keyboardType="number-pad" value={unique.lostContactSince || ''} onChangeText={(t) => setU('lostContactSince', t)} />

          <Text style={styles.subLabel}>Find My …</Text>
          <Field label="Bench Mate" icon="people-outline" value={unique.benchMate || ''} onChangeText={(t) => setU('benchMate', t)} />
          <Field label="Hostel Mate" icon="bed-outline" value={unique.hostelMate || ''} onChangeText={(t) => setU('hostelMate', t)} />
          <Field label="Roommate" icon="home-outline" value={unique.roommate || ''} onChangeText={(t) => setU('roommate', t)} />
          <Field label="Project Team" icon="construct-outline" value={unique.projectTeam || ''} onChangeText={(t) => setU('projectTeam', t)} />
          <Field label="Bus Friend" icon="bus-outline" value={unique.busFriend || ''} onChangeText={(t) => setU('busFriend', t)} />
          <Field label="Lab Partner" icon="flask-outline" value={unique.labPartner || ''} onChangeText={(t) => setU('labPartner', t)} />
          <Field label="Class Monitor" icon="ribbon-outline" value={unique.classMonitor || ''} onChangeText={(t) => setU('classMonitor', t)} />

          <Toggle label="Hidden (Private) Fields" icon="eye-off-outline" hint="Keep these memory details visible only to you." value={!!unique.hiddenFields} onValueChange={(v) => setU('hiddenFields', v)} />
        </>)}

        {show('premium') && (<>
          <SectionTitle>Premium Features</SectionTitle>
          <Pressable onPress={() => router.push('/premium')} style={styles.premiumCard}>
            <View style={{ flex: 1 }}>
              <Text style={styles.premiumTitle}>{state.premium ? '⭐ Premium Active' : 'Upgrade to Premium'}</Text>
              <Text style={styles.premiumSub}>{state.premium ? 'You have unlimited access.' : 'See who viewed you, unlimited chats & filters.'}</Text>
            </View>
            <Ionicons name="chevron-forward" size={22} color="#fff" />
          </Pressable>
          <View style={{ marginTop: 10 }}>
            {PREMIUM_FEATURES.map((f) => (
              <View key={f.label} style={styles.featureRow}>
                <Ionicons name={f.icon} size={18} color={colors.gold} />
                <Text style={styles.featureText}>{f.label}</Text>
                {state.premium
                  ? <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                  : <Ionicons name="lock-closed" size={15} color={colors.muted} />}
              </View>
            ))}
          </View>
        </>)}

        <Button title="Save Changes" icon="checkmark-circle" onPress={save} style={{ marginTop: 18 }} />
        <View style={{ height: 30 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// Verified badge / "Verify via OTP" button shown under mobile & email fields.
function VerifyRow({ verified, canVerify, onVerify, label }) {
  if (verified) {
    return (
      <View style={styles.verifyRow}>
        <Ionicons name="checkmark-circle" size={16} color={colors.success} />
        <Text style={[styles.verifyText, { color: colors.success }]}>Verified</Text>
      </View>
    );
  }
  return (
    <Pressable style={styles.verifyRow} onPress={canVerify ? onVerify : undefined}>
      <Ionicons name="alert-circle-outline" size={16} color={canVerify ? colors.primary : colors.muted} />
      <Text style={[styles.verifyText, { color: canVerify ? colors.primary : colors.muted }]}>Verify {label} via OTP</Text>
    </Pressable>
  );
}

// A dropdown that can flip to free-text entry via a checkbox.
function SelectOrManual({ label, icon, value, options, onChange, placeholder }) {
  const [manual, setManual] = useState(!!value && !options.includes(value));
  return (
    <View>
      {manual ? (
        <Field label={label} icon={icon} value={value} onChangeText={onChange} placeholder={`Enter ${label.toLowerCase()}`} />
      ) : (
        <Select label={label} icon={icon} placeholder={placeholder} value={value} options={options} onChange={onChange} />
      )}
      <Pressable style={styles.checkRow} onPress={() => { setManual((m) => !m); onChange(''); }}>
        <Ionicons name={manual ? 'checkbox' : 'square-outline'} size={20} color={manual ? colors.primary : colors.muted} />
        <Text style={styles.checkText}>Enter manually</Text>
      </Pressable>
    </View>
  );
}

// A tappable settings row with icon + chevron.
function ActionRow({ icon, label, onPress, danger }) {
  return (
    <Pressable style={styles.actionRow} onPress={onPress}>
      <Ionicons name={icon} size={20} color={danger ? colors.danger : colors.body} />
      <Text style={[styles.actionText, danger && { color: colors.danger }]}>{label}</Text>
      <Ionicons name="chevron-forward" size={18} color={colors.muted} />
    </Pressable>
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
  subLabel: { fontWeight: '800', color: colors.ink, fontSize: 14.5, marginTop: 16, marginBottom: 12 },
  premiumCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.gold, borderRadius: 16, padding: 18 },
  premiumTitle: { color: '#fff', fontWeight: '900', fontSize: 16 },
  premiumSub: { color: 'rgba(255,255,255,0.92)', marginTop: 3, fontSize: 13 },
  verifyRow: { flexDirection: 'row', alignItems: 'center', marginTop: -8, marginBottom: 14 },
  verifyText: { fontWeight: '700', fontSize: 13, marginLeft: 6 },
  actionRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, padding: 15, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, marginBottom: 8 },
  actionText: { flex: 1, marginLeft: 12, fontWeight: '700', color: colors.ink, fontSize: 14.5 },
  checkRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 4, marginTop: -8, marginBottom: 14 },
  checkText: { marginLeft: 10, fontWeight: '700', color: colors.ink, fontSize: 14 },
  infoStat: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.successSoft, borderRadius: radius.sm, padding: 14, marginBottom: 16 },
  infoStatText: { marginLeft: 10, fontWeight: '800', color: colors.ink, fontSize: 14 },
  featureRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, padding: 14, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, marginBottom: 8 },
  featureText: { flex: 1, marginLeft: 12, fontWeight: '700', color: colors.ink, fontSize: 14 },
});
