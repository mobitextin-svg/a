import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, Avatar, Select, Toggle, Card, Tag, SectionTitle } from '../src/components/ui';
import EducationForm from '../src/components/EducationForm';
import { colors } from '../src/theme';
import { GENDERS, eduSummary, eduLocation } from '../src/data';
import { useApp } from '../src/store';

// Edit basic information + manage education records after sign-up.
export default function EditProfile() {
  const router = useRouter();
  const { state, updateProfile, addEducation, removeEducation } = useApp();
  const me = state.me || {};

  const [name, setName] = useState(me.name || '');
  const [nickname, setNickname] = useState(me.nickname || '');
  const [gender, setGender] = useState(me.gender || '');
  const [dob, setDob] = useState(me.dob || '');
  const [mobile, setMobile] = useState(me.mobile || '');
  const [email, setEmail] = useState(me.email || '');
  const [mobileHidden, setMobileHidden] = useState(me.mobileHidden ?? true);
  const [emailHidden, setEmailHidden] = useState(me.emailHidden ?? true);
  const [city, setCity] = useState(me.city || '');
  const [state2, setState2] = useState(me.state || '');

  const save = () => {
    updateProfile({
      name: name.trim() || me.name,
      nickname: nickname.trim(),
      gender,
      dob: dob.trim(),
      mobile: mobile.trim(),
      email: email.trim(),
      mobileHidden,
      emailHidden,
      city: city.trim(),
      state: state2.trim(),
    });
    router.back();
  };

  const education = me.education || [];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8}><Ionicons name="chevron-back" size={26} color={colors.ink} /></Pressable>
        <Text style={styles.headerTitle}>Edit Profile</Text>
        <Pressable onPress={save} hitSlop={8}><Text style={styles.save}>Save</Text></Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        <View style={styles.photoRow}>
          <Avatar name={name || '?'} size={84} />
          <Pressable style={styles.photoBtn}>
            <Ionicons name="camera" size={18} color={colors.primary} />
            <Text style={styles.photoText}>Change Photo</Text>
          </Pressable>
        </View>

        <SectionTitle>Basic Information</SectionTitle>
        <Field label="Full Name *" icon="person-outline" value={name} onChangeText={setName} />
        <Field label="Nickname (optional)" icon="happy-outline" value={nickname} onChangeText={setNickname} />
        <Select label="Gender" icon="male-female-outline" placeholder="Select gender" value={gender} options={GENDERS} onChange={setGender} />
        <Field label="Date of Birth" icon="calendar-outline" placeholder="DD / MM / YYYY" value={dob} onChangeText={setDob} />
        <Field label="Mobile Number" icon="call-outline" keyboardType="phone-pad" value={mobile} onChangeText={setMobile} />
        <Toggle label="Hide mobile number" icon="eye-off-outline" value={mobileHidden} onValueChange={setMobileHidden} />
        <Field label="Email ID" icon="mail-outline" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail} />
        <Toggle label="Hide email ID" icon="eye-off-outline" value={emailHidden} onValueChange={setEmailHidden} />
        <Field label="City" icon="location-outline" value={city} onChangeText={setCity} />
        <Field label="State" icon="map-outline" value={state2} onChangeText={setState2} />

        <SectionTitle>Education Records</SectionTitle>
        {education.map((e, i) => (
          <Card key={i} style={{ marginBottom: 10, flexDirection: 'row', alignItems: 'center' }}>
            <Ionicons name="school" size={20} color={colors.primary} style={{ marginRight: 12 }} />
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

        <Text style={styles.addTitle}>Add a record</Text>
        <EducationForm onAdd={addEducation} />

        <Button title="Save Changes" icon="checkmark-circle" onPress={save} style={{ marginTop: 16 }} />
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
  photoBtn: { flexDirection: 'row', alignItems: 'center', marginLeft: 18, backgroundColor: colors.primarySoft, paddingVertical: 10, paddingHorizontal: 16, borderRadius: 12 },
  photoText: { color: colors.primary, fontWeight: '800', marginLeft: 7 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
  addTitle: { fontWeight: '800', color: colors.ink, fontSize: 14.5, marginTop: 10, marginBottom: 12 },
});
