import {
  Box,
  CloseButton,
  Flex,
  FlexProps,
  Icon,
  Link,
  Text,
  VStack,
  useColorModeValue
} from '@chakra-ui/react';
import { IconType } from 'react-icons';
import {
  FiActivity,
  FiAperture,
  FiBarChart2,
  FiFolder,
  FiHome,
  FiSettings,
  FiShield
} from 'react-icons/fi';
import { NavLink } from 'react-router-dom';
import useAuthStore, { Role } from '../../state/authStore';

export interface NavItemConfig {
  label: string;
  description: string;
  to: string;
  icon: IconType;
  roles: Role[];
}

export const navItems: NavItemConfig[] = [
  {
    label: 'Landing',
    description: 'Environment status and recent activity',
    to: '/',
    icon: FiHome,
    roles: ['artist', 'reviewer', 'producer', 'admin']
  },
  {
    label: 'Projects',
    description: 'Portfolio metrics & project analytics',
    to: '/dashboards/projects',
    icon: FiBarChart2,
    roles: ['producer', 'admin']
  },
  {
    label: 'Artist Workload',
    description: 'Assignments and reviews queued',
    to: '/dashboards/workload',
    icon: FiActivity,
    roles: ['artist', 'reviewer', 'producer']
  },
  {
    label: 'Asset Browser',
    description: 'Search and manage assets',
    to: '/discovery/assets',
    icon: FiFolder,
    roles: ['artist', 'reviewer', 'producer', 'admin']
  },
  {
    label: 'Workflow Board',
    description: 'Manage changelists and reviews',
    to: '/workflow/board',
    icon: FiAperture,
    roles: ['artist', 'reviewer', 'producer']
  },
  {
    label: 'Operations',
    description: 'Storage and pipeline health',
    to: '/operations/overview',
    icon: FiShield,
    roles: ['producer', 'admin']
  },
  {
    label: 'Settings',
    description: 'User & integration preferences',
    to: '/settings/preferences',
    icon: FiSettings,
    roles: ['artist', 'reviewer', 'producer', 'admin']
  }
];

interface SidebarProps extends FlexProps {
  onClose: () => void;
}

const Sidebar = ({ onClose, ...rest }: SidebarProps) => {
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const role = useAuthStore((state) => state.role);

  return (
    <Flex
      direction="column"
      borderRightWidth="1px"
      borderColor={borderColor}
      w={{ base: 'full', md: 72 }}
      pos="fixed"
      h="full"
      {...rest}
    >
      <Flex h="20" alignItems="center" mx="8" justifyContent="space-between">
        <Text fontSize="lg" fontWeight="bold">
          Game Asset Portal
        </Text>
        <CloseButton display={{ base: 'flex', md: 'none' }} onClick={onClose} />
      </Flex>
      <VStack align="stretch" spacing={1} px={3} pb={8} overflowY="auto">
        {navItems
          .filter((item) => item.roles.includes(role))
          .map((item) => (
            <NavItem key={item.to} item={item} onNavigate={onClose} />
          ))}
      </VStack>
    </Flex>
  );
};

const NavItem = ({ item, onNavigate }: { item: NavItemConfig; onNavigate: () => void }) => {
  const activeBg = useColorModeValue('purple.100', 'purple.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const textColor = useColorModeValue('gray.700', 'gray.200');

  return (
    <Link
      as={NavLink}
      to={item.to}
      display="flex"
      alignItems="center"
      px={3}
      py={2.5}
      borderRadius="md"
      gap={3}
      _hover={{ textDecoration: 'none', bg: hoverBg }}
      _activeLink={{ bg: activeBg, color: useColorModeValue('purple.900', 'white') }}
      color={textColor}
      onClick={onNavigate}
    >
      <Icon as={item.icon} boxSize={5} />
      <Box>
        <Text fontWeight="medium">{item.label}</Text>
        <Text fontSize="xs" color={useColorModeValue('gray.500', 'gray.400')}>
          {item.description}
        </Text>
      </Box>
    </Link>
  );
};

export default Sidebar;
