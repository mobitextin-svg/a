import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button } from '../../src/components/ui';
import { colors } from '../../src/theme';

export default function Welcome() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.wrap}>
      <View style={styles.hero}>
        <View style={styles.logo}>
          <Ionicons name="school" size={40} color="#fff" />
        </View>
        <Text style={styles.brand}>BatchMate</Text>
        <Text style={styles.tagline}>Reconnect with old classmates from school, college, polytechnic &amp; university.</Text>

        <View style={styles.bullets}>
          {[
            ['search', 'Smart batch & college search'],
            ['people', 'Find your exact batchmates'],
            ['chatbubbles', 'Chat & plan reunions'],
          ].map(([icon, text]) => (
            <View key={icon} style={styles.bullet}>
              <View style={styles.bulletIcon}>
                <Ionicons name={icon} size={18} color={colors.primary} />
              </View>
              <Text style={styles.bulletText}>{text}</Text>
            </View>
          ))}
        </View>
      </View>

      <View style={styles.footer}>
        <Button title="Get Started" icon="arrow-forward" onPress={() => router.push('/(auth)/login')} />
        <Text style={styles.terms}>By continuing you agree to our Terms & Privacy Policy.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.primary, justifyContent: 'space-between' },
  hero: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28 },
  logo: { width: 84, height: 84, borderRadius: 26, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 20 },
  brand: { fontSize: 40, fontWeight: '900', color: '#fff', letterSpacing: -1 },
  tagline: { color: 'rgba(255,255,255,0.9)', textAlign: 'center', fontSize: 16, marginTop: 12, lineHeight: 24, maxWidth: 340 },
  bullets: { marginTop: 36, alignSelf: 'stretch', gap: 14 },
  bullet: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.12)', padding: 14, borderRadius: 16 },
  bulletIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  bulletText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  footer: { backgroundColor: colors.card, padding: 24, borderTopLeftRadius: 28, borderTopRightRadius: 28 },
  terms: { color: colors.muted, textAlign: 'center', fontSize: 12, marginTop: 14 },
});
