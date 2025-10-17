import { create } from 'zustand';

type Role = 'artist' | 'reviewer' | 'producer' | 'admin';

interface AuthState {
  role: Role;
  setRole: (role: Role) => void;
}

const useAuthStore = create<AuthState>((set) => ({
  role: 'artist',
  setRole: (role) => set({ role })
}));

export type { Role };
export default useAuthStore;
