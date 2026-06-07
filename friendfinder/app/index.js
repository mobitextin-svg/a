import React from 'react';
import { Redirect } from 'expo-router';
import { useApp } from '../src/store';
import { Loader } from '../src/components/ui';

// Entry point: wait for persisted state, then route to app or onboarding.
export default function Index() {
  const { hydrated, state } = useApp();
  if (!hydrated) return <Loader />;
  return <Redirect href={state.me ? '/(tabs)' : '/(auth)/welcome'} />;
}
