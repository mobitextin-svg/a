import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { AppProvider } from '../src/store';
import { colors } from '../src/theme';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AppProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="(auth)" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="user/[id]" options={{ presentation: 'card' }} />
            <Stack.Screen name="chat/[id]" />
            <Stack.Screen name="group/[id]" />
            <Stack.Screen name="reunion/[id]" />
            <Stack.Screen name="premium" options={{ presentation: 'modal' }} />
            <Stack.Screen name="edit-profile" options={{ presentation: 'card' }} />
            <Stack.Screen name="account/change-password" options={{ presentation: 'card' }} />
            <Stack.Screen name="account/delete-account" options={{ presentation: 'card' }} />
            <Stack.Screen name="account/verify" options={{ presentation: 'card' }} />
            <Stack.Screen name="deactivated" options={{ presentation: 'card', gestureEnabled: false }} />
          </Stack>
        </AppProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
