import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, Avatar, Select, Toggle } from '../../src/components/ui';
import { colors } from '../../src/theme';
import { GENDERS } from '../../src/data';

// Step 1 of profile setup: basic information.
export default function Register() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [nickname, setNickname] = useState('');
  const [gender, setGender] = useState('');
  const [dob, setDob] = useState('');
  const [mobile, setMobile] = useState('');
  const [email, setEmail] = useState('');
  const [mobileHidden, setMobileHidden] = useState(true);
  const [emailHidden, setEmailHidden] = useState(true);
  const [city, setCity] = useState('');
  const [state, setState] = useState('');

  const next = () => {
    if (!name.trim()) return;
    router.push({
      pathname: '/(auth)/education',
      params: {
        name: name.trim(),
        nickname: nickname.trim(),
        gender,
        dob: dob.trim(),
        mobile: mobile.trim(),
        email: email.trim(),
        mobileHidden: mobileHidden ? '1' : '',
        emailHidden: emailHidden ? '1' : '',
        city: city.trim(),
        state: state.trim(),
      },
    });
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        <Text style={styles.step}>STEP 1 OF 2</Text>
        <Text style={styles.title}>Basic Information</Text>
        <Text style={styles.sub}>This is how old friends will recognise you.</Text>

        <View style={styles.photoRow}>
          <Avatar name={name || '?'} size={88} />
          <Pressable style={styles.photoBtn}>
            <Ionicons name="camera" size={18} color={colors.primary} />
            <Text style={styles.photoText}>Add Profile Photo</Text>
          </Pressable>
        </View>

        <Field label="Full Name *" icon="person-outline" placeholder="e.g. Aarav Sharma" value={name} onChangeText={setName} />
        <Field label="Nickname (optional)" icon="happy-outline" placeholder="e.g. Aaru" value={nickname} onChangeText={setNickname} />
        <Select label="Gender" icon="male-female-outline" placeholder="Select gender" value={gender} options={GENDERS} onChange={setGender} />
        <Field label="Date of Birth" icon="calendar-outline" placeholder="DD / MM / YYYY" value={dob} onChangeText={setDob} />

        <Field label="Mobile Number" icon="call-outline" keyboardType="phone-pad" placeholder="+91 98765 43210" value={mobile} onChangeText={setMobile} />
        <Toggle label="Hide mobile number" hint="Keep your number private from other members." icon="eye-off-outline" value={mobileHidden} onValueChange={setMobileHidden} />

        <Field label="Email ID" icon="mail-outline" keyboardType="email-address" autoCapitalize="none" placeholder="you@example.com" value={email} onChangeText={setEmail} />
        <Toggle label="Hide email ID" hint="Keep your email private from other members." icon="eye-off-outline" value={emailHidden} onValueChange={setEmailHidden} />

        <Field label="City" icon="location-outline" placeholder="e.g. Chennai" value={city} onChangeText={setCity} />
        <Field label="State" icon="map-outline" placeholder="e.g. Tamil Nadu" value={state} onChangeText={setState} />

        <Button title="Next: Education" icon="arrow-forward" onPress={next} disabled={!name.trim()} style={{ marginTop: 8 }} />
        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 24 },
  step: { color: colors.primary, fontWeight: '800', fontSize: 12, letterSpacing: 1 },
  title: { fontSize: 28, fontWeight: '900', color: colors.ink, marginTop: 6 },
  sub: { color: colors.body, fontSize: 15, marginTop: 6, marginBottom: 22 },
  photoRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 24 },
  photoBtn: { flexDirection: 'row', alignItems: 'center', marginLeft: 18, backgroundColor: colors.primarySoft, paddingVertical: 10, paddingHorizontal: 16, borderRadius: 12 },
  photoText: { color: colors.primary, fontWeight: '800', marginLeft: 7 },
});
