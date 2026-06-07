import React, { useRef, useState, useEffect } from 'react';
import { View, Text, StyleSheet, TextInput, Pressable } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button } from '../../src/components/ui';
import { colors } from '../../src/theme';

// OTP entry. Mocked verification — any 4 digits proceed.
export default function Otp() {
  const router = useRouter();
  const { mobile, skip } = useLocalSearchParams();
  const [digits, setDigits] = useState(['', '', '', '']);
  const [seconds, setSeconds] = useState(30);
  const refs = [useRef(), useRef(), useRef(), useRef()];

  useEffect(() => {
    if (skip) router.replace('/(auth)/register');
  }, [skip]);

  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(t);
  }, []);

  const setDigit = (i, val) => {
    const v = val.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[i] = v;
    setDigits(next);
    if (v && i < 3) refs[i + 1].current?.focus();
  };

  const verify = () => router.replace('/(auth)/register');
  const filled = digits.every((d) => d !== '');

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={styles.wrap}>
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={24} color={colors.ink} />
        </Pressable>
        <Text style={styles.title}>Verify OTP</Text>
        <Text style={styles.sub}>Enter the 4-digit code sent to{'\n'}<Text style={{ fontWeight: '800', color: colors.ink }}>{mobile}</Text></Text>

        <View style={styles.boxes}>
          {digits.map((d, i) => (
            <TextInput
              key={i}
              ref={refs[i]}
              value={d}
              onChangeText={(v) => setDigit(i, v)}
              onKeyPress={({ nativeEvent }) => {
                if (nativeEvent.key === 'Backspace' && !digits[i] && i > 0) refs[i - 1].current?.focus();
              }}
              keyboardType="number-pad"
              maxLength={1}
              style={[styles.box, d && styles.boxFilled]}
            />
          ))}
        </View>

        <Button title="Verify & Continue" icon="checkmark-circle" onPress={verify} disabled={!filled} style={{ marginTop: 28 }} />

        <Text style={styles.resend}>
          {seconds > 0 ? `Resend code in 0:${String(seconds).padStart(2, '0')}` : <Text style={{ color: colors.primary, fontWeight: '800' }} onPress={() => setSeconds(30)}>Resend OTP</Text>}
        </Text>
        <Text style={styles.note}>🔒 Demo: enter any 4 digits to continue.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 24 },
  back: { width: 40, height: 40, justifyContent: 'center', marginBottom: 8 },
  title: { fontSize: 28, fontWeight: '900', color: colors.ink },
  sub: { color: colors.body, fontSize: 15, marginTop: 8, lineHeight: 24 },
  boxes: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 34, paddingHorizontal: 6 },
  box: {
    width: 62, height: 68, borderRadius: 16, borderWidth: 2, borderColor: colors.border,
    backgroundColor: colors.card, textAlign: 'center', fontSize: 26, fontWeight: '800', color: colors.ink,
  },
  boxFilled: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  resend: { textAlign: 'center', color: colors.muted, marginTop: 22, fontWeight: '600' },
  note: { color: colors.muted, fontSize: 12.5, textAlign: 'center', marginTop: 14 },
});
