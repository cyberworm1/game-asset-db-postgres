import { ReactNode } from 'react';
import {
  Avatar,
  Box,
  Drawer,
  DrawerContent,
  Flex,
  HStack,
  Icon,
  IconButton,
  Menu,
  MenuButton,
  MenuDivider,
  MenuItem,
  MenuList,
  Text,
  VStack,
  useColorMode,
  useColorModeValue,
  useDisclosure
} from '@chakra-ui/react';
import { FiMoon, FiSun, FiMenu } from 'react-icons/fi';
import Sidebar from './Sidebar';
import useAuthStore from '../../state/authStore';

interface AppLayoutProps {
  children: ReactNode;
}

const AppLayout = ({ children }: AppLayoutProps) => {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const { colorMode, toggleColorMode } = useColorMode();
  const setRole = useAuthStore((state) => state.setRole);
  const role = useAuthStore((state) => state.role);
  const bg = useColorModeValue('gray.50', 'gray.900');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  return (
    <Flex minH="100vh" bg={bg} color={useColorModeValue('gray.800', 'gray.100')}>
      <Sidebar onClose={onClose} display={{ base: 'none', md: 'block' }} />
      <Drawer placement="left" onClose={onClose} isOpen={isOpen} size="xs">
        <DrawerContent>
          <Sidebar onClose={onClose} w="full" borderRight="none" />
        </DrawerContent>
      </Drawer>
      <Flex direction="column" flex="1">
        <Flex
          as="header"
          align="center"
          justify="space-between"
          px={{ base: 4, md: 8 }}
          py={{ base: 3, md: 4 }}
          borderBottomWidth="1px"
          borderColor={borderColor}
          bg={useColorModeValue('white', 'gray.800')}
          position="sticky"
          top={0}
          zIndex={10}
        >
          <HStack spacing={4} align="center">
            <IconButton
              aria-label="Open navigation"
              display={{ base: 'inline-flex', md: 'none' }}
              onClick={onOpen}
              icon={<FiMenu />}
            />
            <Box>
              <Text fontWeight="bold">Asset Portal</Text>
              <Text fontSize="sm" color="gray.500">
                Unified studio workflows
              </Text>
            </Box>
          </HStack>
          <HStack spacing={4}>
            <IconButton
              aria-label="Toggle color mode"
              icon={<Icon as={colorMode === 'light' ? FiMoon : FiSun} />}
              onClick={toggleColorMode}
              variant="ghost"
            />
            <Menu>
              <MenuButton>
                <HStack spacing={3}>
                  <Avatar name="Alex Artist" size="sm" />
                  <VStack align="flex-start" spacing={0} display={{ base: 'none', md: 'flex' }}>
                    <Text fontSize="sm" fontWeight="medium">
                      Alex Artist
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      {role.charAt(0).toUpperCase() + role.slice(1)}
                    </Text>
                  </VStack>
                </HStack>
              </MenuButton>
              <MenuList>
                <MenuItem>Profile</MenuItem>
                <MenuItem>Notification Settings</MenuItem>
                <MenuDivider />
                <MenuItem onClick={() => setRole('artist')}>Switch to Artist</MenuItem>
                <MenuItem onClick={() => setRole('reviewer')}>Switch to Reviewer</MenuItem>
                <MenuItem onClick={() => setRole('producer')}>Switch to Producer</MenuItem>
                <MenuItem onClick={() => setRole('admin')}>Switch to Admin</MenuItem>
                <MenuDivider />
                <MenuItem>Sign out</MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </Flex>
        <Box as="main" flex="1" p={{ base: 4, md: 8 }}>
          {children}
        </Box>
      </Flex>
    </Flex>
  );
};

export default AppLayout;
