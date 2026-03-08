'use client';

import { useEffect, useState } from 'react';

type StorageKind = 'local' | 'session';

interface UsePersistentStateOptions<T> {
  storage?: StorageKind;
  serialize?: (value: T) => string;
  deserialize?: (value: string) => T;
}

function getStorage(kind: StorageKind): Storage | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return kind === 'local' ? window.localStorage : window.sessionStorage;
}

export function usePersistentState<T>(
  key: string,
  initialValue: T,
  options: UsePersistentStateOptions<T> = {},
) {
  const {
    storage = 'session',
    serialize = JSON.stringify,
    deserialize = JSON.parse as (value: string) => T,
  } = options;

  const [value, setValue] = useState<T>(() => {
    const target = getStorage(storage);
    if (!target) {
      return initialValue;
    }

    const saved = target.getItem(key);
    if (!saved) {
      return initialValue;
    }

    try {
      return deserialize(saved);
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    const target = getStorage(storage);
    if (!target) {
      return;
    }

    target.setItem(key, serialize(value));
  }, [key, serialize, storage, value]);

  return [value, setValue] as const;
}
