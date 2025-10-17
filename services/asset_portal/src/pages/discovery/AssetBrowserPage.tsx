import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Divider,
  Flex,
  Heading,
  HStack,
  Input,
  Select,
  SimpleGrid,
  Stack,
  Tag,
  Text,
  Wrap,
  WrapItem
} from '@chakra-ui/react';

const filters = {
  projects: ['Project Odyssey', 'Lego Racing', 'Neon Skies'],
  departments: ['Characters', 'Environments', 'FX', 'Cinematics'],
  assetTypes: ['Model', 'Texture', 'Rig', 'Animation'],
  status: ['In progress', 'Review', 'Approved', 'Retired']
};

const results = [
  {
    name: 'Hero mech rig v4',
    project: 'Project Odyssey',
    department: 'Characters',
    tags: ['rig', 'mech', 'gameplay'],
    status: 'Review'
  },
  {
    name: 'Hangar lighting pass',
    project: 'Project Odyssey',
    department: 'Environments',
    tags: ['lighting', 'cinematic'],
    status: 'In progress'
  },
  {
    name: 'Retro hoverboard texture',
    project: 'Lego Racing',
    department: 'FX',
    tags: ['texture', 'surface'],
    status: 'Approved'
  }
];

const AssetBrowserPage = () => {
  return (
    <Flex gap={6} direction={{ base: 'column', xl: 'row' }} align="flex-start">
      <Card w={{ base: 'full', xl: 'sm' }}>
        <CardHeader>
          <Heading size="sm">Filters</Heading>
        </CardHeader>
        <CardBody>
          <Stack spacing={5}>
            <Box>
              <Text fontWeight="medium">Search</Text>
              <Input placeholder="Search assets, tags, metadata" mt={2} />
            </Box>
            <Box>
              <Text fontWeight="medium">Project</Text>
              <Select mt={2} placeholder="All projects">
                {filters.projects.map((project) => (
                  <option key={project}>{project}</option>
                ))}
              </Select>
            </Box>
            <Box>
              <Text fontWeight="medium">Department</Text>
              <Stack mt={2} spacing={1}>
                {filters.departments.map((department) => (
                  <Checkbox key={department}>{department}</Checkbox>
                ))}
              </Stack>
            </Box>
            <Box>
              <Text fontWeight="medium">Asset type</Text>
              <Stack mt={2} spacing={1}>
                {filters.assetTypes.map((type) => (
                  <Checkbox key={type}>{type}</Checkbox>
                ))}
              </Stack>
            </Box>
            <Box>
              <Text fontWeight="medium">Status</Text>
              <Stack mt={2} spacing={1}>
                {filters.status.map((status) => (
                  <Checkbox key={status}>{status}</Checkbox>
                ))}
              </Stack>
            </Box>
            <Divider />
            <Stack direction={{ base: 'column', sm: 'row' }} spacing={3}>
              <Button colorScheme="purple" flex={1}>
                Apply filters
              </Button>
              <Button variant="ghost" flex={1}>
                Save search
              </Button>
            </Stack>
          </Stack>
        </CardBody>
      </Card>
      <Stack spacing={4} flex={1}>
        <Flex justify="space-between" align="center">
          <Heading size="md">Search results</Heading>
          <HStack>
            <Button variant="outline">Bulk actions</Button>
            <Button colorScheme="purple">Create smart collection</Button>
          </HStack>
        </Flex>
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
          {results.map((asset) => (
            <Card key={asset.name} variant="outline">
              <CardHeader>
                <Stack spacing={1}>
                  <Heading size="sm">{asset.name}</Heading>
                  <Text fontSize="sm" color="gray.500">
                    {asset.project} · {asset.department}
                  </Text>
                </Stack>
              </CardHeader>
              <CardBody>
                <Stack spacing={3}>
                  <Badge colorScheme={asset.status === 'Approved' ? 'green' : 'purple'} w="fit-content">
                    {asset.status}
                  </Badge>
                  <Wrap spacing={2}>
                    {asset.tags.map((tag) => (
                      <WrapItem key={tag}>
                        <Tag colorScheme="purple" variant="subtle">
                          {tag}
                        </Tag>
                      </WrapItem>
                    ))}
                  </Wrap>
                  <Button variant="outline" colorScheme="purple">
                    Open detail view
                  </Button>
                </Stack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
      </Stack>
    </Flex>
  );
};

export default AssetBrowserPage;
