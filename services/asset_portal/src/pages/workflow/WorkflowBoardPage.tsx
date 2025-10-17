import {
  Badge,
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  SimpleGrid,
  Stack,
  Text
} from '@chakra-ui/react';

const columns = [
  {
    title: 'Ready for review',
    items: [
      { id: 'CL-4271', description: 'Mech rig retarget · Project Odyssey', priority: 'High' },
      { id: 'CL-4272', description: 'Hangar lighting adjustments · Project Odyssey', priority: 'Medium' }
    ]
  },
  {
    title: 'In review',
    items: [
      { id: 'CL-4268', description: 'Hoverboard texture polish · Lego Racing', priority: 'High' }
    ]
  },
  {
    title: 'Change requested',
    items: [{ id: 'CL-4260', description: 'Cinematic FX sparks v2 · Neon Skies', priority: 'Medium' }]
  },
  {
    title: 'Merge ready',
    items: [{ id: 'CL-4245', description: 'Environment props cleanup · Project Odyssey', priority: 'Low' }]
  }
];

const WorkflowBoardPage = () => (
  <SimpleGrid columns={{ base: 1, lg: 2, xl: 4 }} spacing={4} alignItems="flex-start">
    {columns.map((column) => (
      <Card key={column.title} minH="xs">
        <CardHeader>
          <Heading size="sm">{column.title}</Heading>
        </CardHeader>
        <CardBody>
          <Stack spacing={3}>
            {column.items.map((item) => (
              <Box key={item.id} borderWidth="1px" borderRadius="md" p={3}>
                <Stack spacing={1}>
                  <Text fontWeight="semibold">{item.id}</Text>
                  <Text fontSize="sm" color="gray.500">
                    {item.description}
                  </Text>
                  <Badge colorScheme={item.priority === 'High' ? 'red' : item.priority === 'Medium' ? 'orange' : 'green'}>
                    {item.priority} priority
                  </Badge>
                </Stack>
              </Box>
            ))}
          </Stack>
        </CardBody>
      </Card>
    ))}
  </SimpleGrid>
);

export default WorkflowBoardPage;
