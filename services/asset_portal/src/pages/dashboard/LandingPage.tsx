import {
  Badge,
  Box,
  Card,
  CardBody,
  CardHeader,
  Grid,
  GridItem,
  Heading,
  HStack,
  Icon,
  List,
  ListItem,
  SimpleGrid,
  Stack,
  Text,
  useColorModeValue
} from '@chakra-ui/react';
import { FiArrowRight, FiCheckCircle, FiClock, FiServer } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';

const LandingPage = () => {
  const statusColor = useColorModeValue('green.500', 'green.300');
  const activity = [
    {
      id: 1,
      title: 'Texture pack v12 submitted to Review Board',
      timestamp: '5 minutes ago',
      by: 'Morgan Reviewer'
    },
    {
      id: 2,
      title: 'New cinematic branch created for Project Odyssey',
      timestamp: '32 minutes ago',
      by: 'Priya Producer'
    },
    {
      id: 3,
      title: 'Storage audit completed - 78% utilization',
      timestamp: '1 hour ago',
      by: 'Ops Automation'
    }
  ];

  const quickLinks = [
    {
      label: 'Review backlog',
      description: '12 items awaiting your approval',
      to: '/workflow/board'
    },
    {
      label: 'Asset browser',
      description: 'Search textures, rigs, and FX assets',
      to: '/discovery/assets'
    },
    {
      label: 'Project health',
      description: 'Track progress vs. production targets',
      to: '/dashboards/projects'
    }
  ];

  return (
    <Stack spacing={8}>
      <Heading size="lg">Studio control center</Heading>
      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
        <Card>
          <CardHeader>
            <HStack spacing={3}>
              <Icon as={FiServer} color={statusColor} boxSize={5} />
              <Heading size="sm">Environment status</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <Stack spacing={3}>
              <Text>
                Production systems are{' '}
                <Box as="span" color={statusColor} fontWeight="bold">
                  Operational
                </Box>
              </Text>
              <Stack spacing={1}>
                <Text fontSize="sm" color="gray.500">
                  Last incident
                </Text>
                <Text fontSize="sm">12 days ago · CDN edge cache invalidation</Text>
              </Stack>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <HStack spacing={3}>
              <Icon as={FiClock} boxSize={5} />
              <Heading size="sm">Upcoming deadlines</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <Stack spacing={3}>
              <Text fontSize="sm">Lego Racing seasonal drop — review freeze in 2 days</Text>
              <Text fontSize="sm">Odyssey cinematic milestone — merge cut on Friday</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <HStack spacing={3}>
              <Icon as={FiCheckCircle} boxSize={5} />
              <Heading size="sm">Workflow summary</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <Stack spacing={3}>
              <Text fontSize="sm">27 active changelists · 9 pending reviews · 4 merge conflicts</Text>
              <Text fontSize="sm">Jobs queue latency stable (p95: 1m 12s)</Text>
            </Stack>
          </CardBody>
        </Card>
      </SimpleGrid>
      <Grid templateColumns={{ base: '1fr', lg: '2fr 1fr' }} gap={6} alignItems="flex-start">
        <GridItem>
          <Card>
            <CardHeader>
              <Heading size="sm">Recent activity</Heading>
            </CardHeader>
            <CardBody>
              <List spacing={4}>
                {activity.map((item) => (
                  <ListItem key={item.id}>
                    <Stack spacing={1}>
                      <Text fontWeight="medium">{item.title}</Text>
                      <Text fontSize="sm" color="gray.500">
                        {item.timestamp} · {item.by}
                      </Text>
                    </Stack>
                  </ListItem>
                ))}
              </List>
            </CardBody>
          </Card>
        </GridItem>
        <GridItem>
          <Card>
            <CardHeader>
              <Heading size="sm">Quick links</Heading>
            </CardHeader>
            <CardBody>
              <Stack spacing={4}>
                {quickLinks.map((link) => (
                  <Box
                    key={link.to}
                    as={RouterLink}
                    to={link.to}
                    borderWidth="1px"
                    borderRadius="lg"
                    p={4}
                    _hover={{ textDecoration: 'none', borderColor: useColorModeValue('purple.400', 'purple.300') }}
                  >
                    <HStack justify="space-between" align="start">
                      <Box>
                        <Text fontWeight="medium">{link.label}</Text>
                        <Text fontSize="sm" color="gray.500">
                          {link.description}
                        </Text>
                      </Box>
                      <Icon as={FiArrowRight} />
                    </HStack>
                  </Box>
                ))}
              </Stack>
            </CardBody>
          </Card>
          <Card mt={6}>
            <CardHeader>
              <Heading size="sm">Deployment channel</Heading>
            </CardHeader>
            <CardBody>
              <Stack spacing={3}>
                <HStack>
                  <Badge colorScheme="green">Staging</Badge>
                  <Text fontSize="sm">1.3.0-rc2</Text>
                </HStack>
                <Text fontSize="sm" color="gray.500">
                  Last promoted 3 hours ago by CI pipeline #268
                </Text>
              </Stack>
            </CardBody>
          </Card>
        </GridItem>
      </Grid>
    </Stack>
  );
};

export default LandingPage;
