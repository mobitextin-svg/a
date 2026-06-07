import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button } from '../src/components/ui';
import { colors, radius } from '../src/theme';
import { useApp } from '../src/store';

const PERKS = [
  ['eye', 'See who searched & viewed your profile'],
  ['chatbubbles', 'Unlimited messaging to anyone'],
  ['options', 'Advanced search filters'],
  ['swap-horizontal', 'Contact exchange requests'],
  ['storefront', 'Full alumni business directory'],
  ['sparkles', 'Priority AI recommendations'],
];

export default function Premium() {
  const router = useRouter();
  const { state, upgrade } = useApp();

  const doUpgrade = () => { upgrade(); router.back(); };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.primary }}>
      <ScrollView contentContainerStyle={{ flexGrow: 1 }}>
        <Pressable onPress={() => router.back()} style={styles.close}><Ionicons name="close" size={24} color="#fff" /></Pressable>

        <View style={styles.hero}>
          <View style={styles.crown}><Ionicons name="star" size={36} color={colors.gold} /></View>
          <Text style={styles.title}>BatchMate Premium</Text>
          <Text style={styles.sub}>Unlock the full power of reconnecting</Text>
        </View>

        <View style={styles.sheet}>
          {PERKS.map(([icon, text]) => (
            <View key={text} style={styles.perk}>
              <View style={styles.perkIcon}><Ionicons name={icon} size={18} color={colors.primary} /></View>
              <Text style={styles.perkText}>{text}</Text>
              <Ionicons name="checkmark-circle" size={20} color={colors.success} />
            </View>
          ))}

          <View style={styles.priceCard}>
            <View>
              <Text style={styles.price}>₹99<Text style={styles.per}>/month</Text></Text>
              <Text style={styles.priceNote}>Cancel anytime</Text>
            </View>
            <View style={styles.badge}><Text style={styles.badgeText}>BEST VALUE</Text></View>
          </View>

          {state.premium ? (
            <Button title="You're Premium ⭐" variant="success" icon="checkmark-circle" onPress={() => router.back()} />
          ) : (
            <Button title="Subscribe for ₹99/month" icon="card" onPress={doUpgrade} />
          )}
          <Text style={styles.legal}>Demo: no real payment is processed. Integrate Razorpay / Google Play / App Store billing for production.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  close: { alignSelf: 'flex-end', padding: 18 },
  hero: { alignItems: 'center', paddingBottom: 26 },
  crown: { width: 78, height: 78, borderRadius: 24, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  title: { fontSize: 28, fontWeight: '900', color: '#fff' },
  sub: { color: 'rgba(255,255,255,0.9)', marginTop: 6, fontSize: 15 },
  sheet: { backgroundColor: colors.bg, borderTopLeftRadius: 30, borderTopRightRadius: 30, padding: 24, flex: 1, minHeight: 460 },
  perk: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, padding: 14, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, marginBottom: 10 },
  perkIcon: { width: 36, height: 36, borderRadius: 11, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  perkText: { flex: 1, fontWeight: '700', color: colors.ink, fontSize: 14.5 },
  priceCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.primarySoft, borderRadius: radius.md, padding: 20, marginTop: 12, marginBottom: 18, borderWidth: 1.5, borderColor: colors.primary },
  price: { fontSize: 34, fontWeight: '900', color: colors.ink },
  per: { fontSize: 16, color: colors.muted, fontWeight: '700' },
  priceNote: { color: colors.muted, marginTop: 2 },
  badge: { backgroundColor: colors.gold, paddingVertical: 6, paddingHorizontal: 12, borderRadius: radius.pill },
  badgeText: { color: '#fff', fontWeight: '900', fontSize: 11 },
  legal: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 16, lineHeight: 18 },
});
