import React, { useState } from 'react';
import { View, Text, StyleSheet, Pressable, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field } from '../../src/components/ui';
import { colors } from '../../src/theme';

// Login screen — mobile OTP / email / Google.
// NOTE: OTP & Google are mocked. Wire to your SMS gateway (e.g. MSG91/Twilio)
// and expo-auth-session / Firebase for production.
export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState('mobile');
  const [mobile, setMobile] = useState('');
  const [email, setEmail] = useState('');

  const continueMobile = () => {
    if (mobile.replace(/\D/g, '').length < 10) return;
    router.push({ pathname: '/(auth)/otp', params: { mobile } });
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={24} color={colors.ink} />
        </Pressable>

        <Text style={styles.title}>Welcome back 👋</Text>
        <Text style={styles.sub}>Log in to find and reconnect with your batchmates.</Text>

        <View style={styles.tabs}>
          {[['mobile', 'Mobile'], ['email', 'Email']].map(([key, label]) => (
            <Pressable key={key} onPress={() => setMode(key)} style={[styles.tab, mode === key && styles.tabActive]}>
              <Text style={[styles.tabText, mode === key && styles.tabTextActive]}>{label}</Text>
            </Pressable>
          ))}
        </View>

        {mode === 'mobile' ? (
          <>
            <Field label="Mobile Number" icon="call-outline" keyboardType="phone-pad" placeholder="+91 98765 43210" value={mobile} onChangeText={setMobile} />
            <Button title="Send OTP" icon="arrow-forward" onPress={continueMobile} />
          </>
        ) : (
          <>
            <Field label="Email Address" icon="mail-outline" keyboardType="email-address" autoCapitalize="none" placeholder="you@example.com" value={email} onChangeText={setEmail} />
            <Button title="Continue" icon="arrow-forward" onPress={() => router.push({ pathname: '/(auth)/otp', params: { mobile: email } })} />
          </>
        )}

        <View style={styles.divider}>
          <View style={styles.line} /><Text style={styles.or}>or</Text><View style={styles.line} />
        </View>

        <Button title="Continue with Google" variant="ghost" icon="logo-google" onPress={() => router.push({ pathname: '/(auth)/otp', params: { mobile: 'google', skip: '1' } })} />

        <Text style={styles.note}>🔒 Demo build: any OTP works. No real SMS is sent.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 24, paddingTop: 8 },
  back: { width: 40, height: 40, justifyContent: 'center', marginBottom: 8 },
  title: { fontSize: 28, fontWeight: '900', color: colors.ink },
  sub: { color: colors.body, fontSize: 15, marginTop: 6, marginBottom: 24, lineHeight: 22 },
  tabs: { flexDirection: 'row', backgroundColor: '#eef1f6', borderRadius: 14, padding: 4, marginBottom: 22 },
  tab: { flex: 1, paddingVertical: 11, borderRadius: 11, alignItems: 'center' },
  tabActive: { backgroundColor: colors.card },
  tabText: { fontWeight: '700', color: colors.muted },
  tabTextActive: { color: colors.ink },
  divider: { flexDirection: 'row', alignItems: 'center', marginVertical: 22 },
  line: { flex: 1, height: 1, backgroundColor: colors.border },
  or: { marginHorizontal: 12, color: colors.muted, fontWeight: '600' },
  note: { color: colors.muted, fontSize: 12.5, textAlign: 'center', marginTop: 22 },
});
